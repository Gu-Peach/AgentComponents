from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.db import models
from app.repositories.sql import DeviceSpecRepository, ProjectRepository, SceneRepository, SimulationRepository
from app.schemas.domain import ActionCompleteRequest, DeviceTaskDispatchRequest, RuntimeSnapshotPut, SignalEmitRequest, SimulationRunCreate
from app.services.action_executor import ActionExecutor, CONVEYOR_BEHAVIORS, CONVEYOR_MOVE_BEHAVIORS
from app.services.device_runtime import DeviceRuntime
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore
from app.services.scene_service import SceneService
from app.services.signal_bus_runtime import SignalBusRuntime


class SimulationService:
    # 初始化仿真服务：保存数据库会话，创建项目/场景/仿真仓储，并注入运行时状态存储。
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.scenes = SceneRepository(db)
        self.simulations = SimulationRepository(db)
        self.device_specs = DeviceSpecRepository(db)
        self.runtime_store = runtime_store

    # 创建仿真运行：校验项目和场景，生成初始快照，保存仿真记录并写入运行时状态。
    def create_run(self, project_id: str, payload: SimulationRunCreate) -> models.SimulationRun:
        if not self.projects.get(project_id):
            raise NotFoundError("Project", project_id)
        scene = self.scenes.get_by_project(project_id)
        if not scene:
            raise NotFoundError("Scene", project_id)
        if payload.base_scene_revision is not None and payload.base_scene_revision != scene.revision:
            raise AppError("SCENE_REVISION_CONFLICT", "Simulation run base revision does not match current scene revision.", 409, {"expected_revision": payload.base_scene_revision, "current_revision": scene.revision})
        scene = self._ensure_topology_before_run(project_id, scene)
        run_id = new_id("simrun")
        snapshot = payload.initial_snapshot or self._initial_snapshot(scene)
        snapshot["run_id"] = run_id
        run = models.SimulationRun(
            id=run_id,
            project_id=project_id,
            scene_id=scene.id,
            base_scene_revision=scene.revision,
            status="created",
            runtime_snapshot=snapshot,
        )
        self.simulations.add_run(run)
        self._enqueue_startup_behavior(run, snapshot, scene.current_document)
        run.runtime_snapshot = snapshot
        self.db.commit()
        self.runtime_store.put_snapshot(run.id, snapshot)
        return run

    # 根据场景运行配置，在创建 run 前确保当前 revision 的 topology_graph 可用。
    def _ensure_topology_before_run(self, project_id: str, scene: models.Scene) -> models.Scene:
        runtime_config = scene.current_document.get("runtime_config", {})
        if runtime_config.get("topology_rebuild_policy") != "before_run":
            return scene
        topology_ref = scene.current_document.get("derived_artifacts", {}).get("topology_graph", {})
        if topology_ref.get("status") == "valid" and topology_ref.get("source_scene_revision") == scene.revision:
            return scene
        SceneService(self.db).rebuild_topology(project_id)
        return self.scenes.get(scene.id) or scene

    # 查询仿真运行：按 run_id 读取仿真记录，不存在则抛出 NotFoundError。
    def get_run(self, run_id: str) -> models.SimulationRun:
        run = self.simulations.get_run(run_id)
        if not run:
            raise NotFoundError("SimulationRun", run_id)
        return run

    # 获取运行时快照：先确认仿真运行存在，再从运行时状态存储中读取 snapshot。
    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        self.get_run(run_id)
        return self.runtime_store.get_snapshot(run_id)

    # 获取前端行为事件：用于前端按 stream 顺序逐条消费并立即触发设备动画。
    def get_frontend_events(self, run_id: str) -> list[dict[str, Any]]:
        self.get_run(run_id)
        return self.runtime_store.get_frontend_events(run_id)

    # 写入运行时快照：更新数据库中的 snapshot，同时同步写入运行时状态存储。
    def put_snapshot(self, run_id: str, payload: RuntimeSnapshotPut) -> dict[str, Any]:
        run = self.get_run(run_id)
        run.runtime_snapshot = payload.snapshot
        self.db.commit()
        self.runtime_store.put_snapshot(run_id, payload.snapshot, payload.ttl_seconds)
        return payload.snapshot

    # 发送信号事件：保存信号最新状态，记录仿真事件，并返回本次信号事件。
    def emit_signal(self, run_id: str, signal_id: str, payload: SignalEmitRequest) -> dict[str, Any]:
        run = self.get_run(run_id)
        result = SignalBusRuntime(self.db, self.runtime_store).emit(run, signal_id, payload)
        self.db.commit()
        return result

    # 分发设备任务：消费 snapshot 中的 pending device_task，生成 active_action 并推进设备状态。
    def dispatch_device_tasks(self, run_id: str, payload: DeviceTaskDispatchRequest) -> dict[str, Any]:
        run = self.get_run(run_id)
        snapshot = deepcopy(self.runtime_store.get_snapshot(run_id) or run.runtime_snapshot or {})
        result = DeviceRuntime(self.device_specs).dispatch_pending_tasks(snapshot, task_ids=payload.task_ids, sim_time_s=payload.sim_time_s)
        self.runtime_store.put_snapshot(run_id, snapshot, payload.ttl_seconds)
        run.runtime_snapshot = snapshot
        for action in result["dispatched_actions"]:
            self.simulations.add_event(
                models.SimulationEvent(
                    id=new_id("simevt"),
                    simulation_run_id=run.id,
                    sim_time_s=payload.sim_time_s,
                    event_type="device_action_started",
                    payload=action,
                )
            )
        self.db.commit()
        return {"run_id": run_id, **result, "snapshot": snapshot}

    def complete_action(self, run_id: str, action_ref: str, payload: ActionCompleteRequest) -> dict[str, Any]:
        run = self.get_run(run_id)
        snapshot = deepcopy(self.runtime_store.get_snapshot(run_id) or run.runtime_snapshot or {})
        result = self._complete_runtime_action(snapshot, action_ref, payload)

        runtime_followups = {"events": [], "device_tasks": [], "frontend_events": []}
        if payload.status == "done" and result.get("status") not in {"not_found", "already_completed"}:
            runtime_followups = self._process_runtime_emitted_events(run, snapshot, result.get("emitted_events", []), payload)

        self.runtime_store.put_snapshot(run_id, snapshot, payload.ttl_seconds)
        run.runtime_snapshot = snapshot
        for event in result.get("events", []) + runtime_followups.get("events", []):
            self.simulations.add_event(
                models.SimulationEvent(
                    id=new_id("simevt"),
                    simulation_run_id=run.id,
                    sim_time_s=payload.sim_time_s,
                    event_type=event.get("type", "device_action_completed"),
                    payload=event,
                )
            )

        completion_signal_results: list[dict[str, Any]] = []
        process_handoff_tasks: list[dict[str, Any]] = []
        process_handoff_frontend_events: list[dict[str, Any]] = []
        if payload.status == "done" and result.get("status") not in {"not_found", "already_completed"}:
            if self._should_emit_completion_signals(snapshot, result):
                completion_signal_results = self._emit_completion_signals(run, result, payload)
            routed_target_instances = {
                task.get("instance_id")
                for signal_result in completion_signal_results
                for task in signal_result.get("device_tasks", [])
            }
            if self._should_enqueue_process_handoffs(snapshot, result):
                snapshot = deepcopy(self.runtime_store.get_snapshot(run_id) or run.runtime_snapshot or snapshot)
                handoff = self._enqueue_process_handoffs(run, snapshot, result, payload, routed_target_instances)
                process_handoff_tasks = handoff["device_tasks"]
                process_handoff_frontend_events = handoff["frontend_events"]
                self.runtime_store.put_snapshot(run_id, snapshot, payload.ttl_seconds)
                run.runtime_snapshot = snapshot
        self.db.commit()
        return {
            "run_id": run_id,
            "action_ref": action_ref,
            **result,
            "runtime_followup_events": runtime_followups.get("events", []),
            "runtime_followup_tasks": runtime_followups.get("device_tasks", []),
            "runtime_followup_frontend_events": runtime_followups.get("frontend_events", []),
            "completion_signal_results": completion_signal_results,
            "process_handoff_tasks": process_handoff_tasks,
            "process_handoff_frontend_events": process_handoff_frontend_events,
            "snapshot": snapshot,
        }

    # 清空运行时状态：确认仿真运行存在后，删除该 run_id 对应的临时运行数据。
    def clear_runtime_state(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        self.runtime_store.clear_run(run_id)
        return {"run_id": run_id, "cleared": True}

    def _enqueue_startup_behavior(
        self,
        run: models.SimulationRun,
        snapshot: dict[str, Any],
        scene_doc: dict[str, Any],
    ) -> dict[str, Any] | None:
        first_behavior = scene_doc.get("runtime_config", {}).get("startup", {}).get("first_behavior")
        if not isinstance(first_behavior, dict):
            return None
        instance_id = first_behavior.get("instance_id")
        behavior_id = first_behavior.get("behavior_id")
        if not instance_id or not behavior_id:
            return None
        instance = self._find_scene_instance(scene_doc, instance_id)
        if not instance or not self._behavior_definition(instance, behavior_id):
            return None
        task_payload = DeviceRuntime._payload_with_instance_runtime_context(first_behavior.get("payload", {}), instance)
        task_payload = ActionExecutor({}, snapshot).prepare_behavior_payload(instance_id, behavior_id, task_payload)
        task = {
            "task_id": new_id("task"),
            "run_id": run.id,
            "instance_id": instance_id,
            "device_type": instance.get("device_type"),
            "trigger_signal": scene_doc.get("runtime_config", {}).get("startup", {}).get("source_event", "runtime.sim_start"),
            "signal_port": None,
            "behavior_id": behavior_id,
            "payload": task_payload,
            "status": "pending",
            "source_signal": "runtime.startup",
            "route_id": "runtime_config.startup.first_behavior",
            "edge_id": None,
            "created_by_event_id": None,
        }
        self.runtime_store.enqueue_device_task(run.id, task)
        self.simulations.add_event(
            models.SimulationEvent(
                id=new_id("simevt"),
                simulation_run_id=run.id,
                sim_time_s=0,
                event_type="device_task_created",
                payload=task,
            )
        )
        snapshot.setdefault("device_tasks", []).append(task)
        self._mark_device_queued(snapshot, instance_id)
        frontend_event = self._publish_frontend_behavior_event(run, task, ActionCompleteRequest(sim_time_s=0), snapshot)
        return {"task": task, "frontend_event": frontend_event}

    def _emit_completion_signals(
        self,
        run: models.SimulationRun,
        completion_result: dict[str, Any],
        request: ActionCompleteRequest,
    ) -> list[dict[str, Any]]:
        completed = self._completed_runtime_item(completion_result)
        if not completed:
            return []
        instance_id = completed.get("instance_id")
        behavior_id = completed.get("behavior_id")
        if not instance_id or not behavior_id:
            return []

        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)
        instance = self._find_scene_instance(scene.current_document, instance_id)
        if not instance:
            return []
        behavior = self._behavior_definition(instance, behavior_id)
        if not behavior:
            return []

        output_signals = self._completion_output_signals(instance, behavior, request.status)
        signal_bus = SignalBusRuntime(self.db, self.runtime_store)
        emitted: list[dict[str, Any]] = []
        for signal_port in output_signals:
            signal_id = f"{instance_id}.{signal_port}"
            signal_payload = self._completion_signal_payload(completed, request, signal_port)
            emitted.append(
                signal_bus.emit(
                    run,
                    signal_id,
                    SignalEmitRequest(
                        value=request.status == "done",
                        payload=signal_payload,
                        sim_time_s=request.sim_time_s,
                        ttl_seconds=request.ttl_seconds,
                    ),
                )
            )
        return emitted

    def _enqueue_process_handoffs(
        self,
        run: models.SimulationRun,
        snapshot: dict[str, Any],
        completion_result: dict[str, Any],
        request: ActionCompleteRequest,
        routed_target_instances: set[str | None],
    ) -> dict[str, list[dict[str, Any]]]:
        completed = self._completed_runtime_item(completion_result)
        if not completed or request.status != "done":
            return {"device_tasks": [], "frontend_events": []}
        instance_id = completed.get("instance_id")
        behavior_id = completed.get("behavior_id")
        if not instance_id or not behavior_id:
            return {"device_tasks": [], "frontend_events": []}

        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)
        source_instance = self._find_scene_instance(scene.current_document, instance_id)
        if not source_instance:
            return {"device_tasks": [], "frontend_events": []}
        behavior = self._behavior_definition(source_instance, behavior_id)
        output_process_port = behavior.get("output_process_port") if behavior else None
        if not output_process_port:
            return {"device_tasks": [], "frontend_events": []}

        source_ref = f"{instance_id}.{output_process_port}"
        created_tasks: list[dict[str, Any]] = []
        frontend_events: list[dict[str, Any]] = []
        source_exit_released = False
        for edge in scene.current_document.get("process_edges", []):
            if edge.get("source") != source_ref:
                continue
            target = self._parse_ref(edge.get("target"))
            if not target:
                continue
            target_instance_id, target_process_port = target
            if target_instance_id in routed_target_instances:
                continue
            target_instance = self._find_scene_instance(scene.current_document, target_instance_id)
            if not target_instance:
                continue
            target_behavior = self._behavior_for_process_input(target_instance, target_process_port)
            if not target_behavior:
                continue

            if not source_exit_released:
                self._release_completed_conveyor_exit_for_handoff(snapshot, completed, request)
                source_exit_released = True

            task_payload = self._process_handoff_payload(completed, request, edge, target_process_port)
            task_payload = DeviceRuntime._payload_with_instance_runtime_context(task_payload, target_instance)
            task_payload = ActionExecutor({}, snapshot).prepare_behavior_payload(target_instance_id, target_behavior.get("behavior_id"), task_payload)
            completion_events = completion_result.get("events") or [{}]
            task = {
                "task_id": new_id("task"),
                "run_id": run.id,
                "instance_id": target_instance_id,
                "device_type": target_instance.get("device_type"),
                "trigger_signal": f"process_handoff:{edge.get('edge_id')}",
                "signal_port": None,
                "behavior_id": target_behavior.get("behavior_id"),
                "payload": task_payload,
                "status": "pending",
                "source_signal": f"completion:{instance_id}.{behavior_id}",
                "route_id": f"process_handoff_{edge.get('edge_id')}",
                "edge_id": edge.get("edge_id"),
                "created_by_event_id": completion_events[-1].get("event_id"),
            }
            self.runtime_store.enqueue_device_task(run.id, task, request.ttl_seconds)
            self.simulations.add_event(
                models.SimulationEvent(
                    id=new_id("simevt"),
                    simulation_run_id=run.id,
                    sim_time_s=request.sim_time_s,
                    event_type="device_task_created",
                    payload=task,
                )
            )
            snapshot.setdefault("device_tasks", []).append(task)
            self._mark_device_queued(snapshot, target_instance_id)
            frontend_event = self._publish_frontend_behavior_event(run, task, request, snapshot)
            created_tasks.append(task)
            if frontend_event:
                frontend_events.append(frontend_event)
        return {"device_tasks": created_tasks, "frontend_events": frontend_events}

    def _behavior_definition(self, instance: dict[str, Any], behavior_id: str) -> dict[str, Any] | None:
        spec = self.device_specs.get(instance.get("spec_id", ""))
        if not spec:
            return None
        return next((behavior for behavior in spec.document.get("transport_behaviors", []) if behavior.get("behavior_id") == behavior_id), None)

    def _behavior_for_process_input(self, instance: dict[str, Any], process_port: str) -> dict[str, Any] | None:
        spec = self.device_specs.get(instance.get("spec_id", ""))
        if not spec:
            return None
        candidates = [
            behavior
            for behavior in spec.document.get("transport_behaviors", [])
            if behavior.get("input_process_port") == process_port
        ]
        return next((behavior for behavior in candidates if behavior.get("behavior_id") == "accept_material"), None) or next(iter(candidates), None)

    def _completion_output_signals(self, instance: dict[str, Any], behavior: dict[str, Any], status: str) -> list[str]:
        if status == "failed":
            return [signal for signal in behavior.get("output_signals", []) if signal == "error"]
        spec = self.device_specs.get(instance.get("spec_id", ""))
        signal_ports = {port.get("port_id"): port for port in (spec.document.get("signal_ports", []) if spec else [])}
        output_signals: list[str] = []
        for signal in behavior.get("output_signals", []):
            if signal in {"busy", "error"}:
                continue
            port = signal_ports.get(signal, {})
            if port.get("direction") not in {None, "output", "bidirectional"}:
                continue
            output_signals.append(signal)
        return output_signals

    @staticmethod
    def _completed_runtime_item(completion_result: dict[str, Any]) -> dict[str, Any] | None:
        return completion_result.get("completed_task") or completion_result.get("completed_action")

    @staticmethod
    def _completion_signal_payload(completed: dict[str, Any], request: ActionCompleteRequest, signal_port: str) -> dict[str, Any]:
        payload = SimulationService._strip_runtime_execution_fields(completed.get("payload", {}))
        payload.update(
            {
                "completed_instance_id": completed.get("instance_id"),
                "completed_behavior_id": completed.get("behavior_id"),
                "completed_task_id": completed.get("task_id"),
                "completed_action_id": completed.get("action_id"),
                "completion_signal_port": signal_port,
                "completion_status": request.status,
                "completion_payload": deepcopy(request.payload),
            }
        )
        return payload

    @staticmethod
    def _process_handoff_payload(
        completed: dict[str, Any],
        request: ActionCompleteRequest,
        edge: dict[str, Any],
        target_process_port: str,
    ) -> dict[str, Any]:
        payload = SimulationService._strip_runtime_execution_fields(completed.get("payload", {}))
        payload.update(
            {
                "source_process_edge": edge.get("edge_id"),
                "source_process_ref": edge.get("source"),
                "target_process_ref": edge.get("target"),
                "target_process_port": target_process_port,
                "completed_instance_id": completed.get("instance_id"),
                "completed_behavior_id": completed.get("behavior_id"),
                "completed_task_id": completed.get("task_id"),
                "completed_action_id": completed.get("action_id"),
                "completion_status": request.status,
                "completion_payload": deepcopy(request.payload),
            }
        )
        return payload

    @staticmethod
    def _strip_runtime_execution_fields(payload: dict[str, Any]) -> dict[str, Any]:
        stripped = deepcopy(payload or {})
        for key in [
            "runtime_geometry",
            "runtime_kinematics",
            "scene_instance",
            "waypoints",
            "from_position",
            "to_position",
            "pick_position",
            "place_position",
        ]:
            stripped.pop(key, None)
        return stripped

    @staticmethod
    def _find_scene_instance(scene_doc: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
        return next((instance for instance in scene_doc.get("instances", []) if instance.get("instance_id") == instance_id), None)

    @staticmethod
    def _parse_ref(ref: str | None) -> tuple[str, str] | None:
        if not ref or "." not in ref:
            return None
        instance_id, port_id = ref.split(".", 1)
        return (instance_id, port_id) if instance_id and port_id else None

    @staticmethod
    def _mark_device_queued(snapshot: dict[str, Any], instance_id: str) -> None:
        device_states = snapshot.setdefault("device_states", {})
        if device_states.get(instance_id) in {None, "idle"}:
            device_states[instance_id] = "queued"
        fsm_states = snapshot.setdefault("device_fsm_states", {})
        if fsm_states.get(instance_id) in {None, "idle"}:
            fsm_states[instance_id] = "queued"

    def _publish_frontend_behavior_event(
        self,
        run: models.SimulationRun,
        task: dict[str, Any],
        request: ActionCompleteRequest,
        snapshot: dict[str, Any],
    ) -> dict[str, Any] | None:
        behavior_id = task.get("behavior_id")
        if not behavior_id:
            return None
        self._prepare_task_for_frontend_runtime(snapshot, task)
        self._apply_task_start_side_effects(snapshot, task)
        event = {
            "event_id": new_id("fevt"),
            "type": "device_behavior_triggered",
            "run_id": run.id,
            "task_id": task["task_id"],
            "instance_id": task["instance_id"],
            "device_type": task.get("device_type"),
            "behavior_id": behavior_id,
            "payload": deepcopy(task.get("payload", {})),
            "status": "queued",
            "sim_time_s": request.sim_time_s,
            "source_signal": task.get("source_signal"),
            "trigger_signal": task.get("trigger_signal"),
            "signal_port": task.get("signal_port"),
            "route_id": task.get("route_id"),
            "edge_id": task.get("edge_id"),
        }
        published = self.runtime_store.publish_frontend_event(run.id, event, request.ttl_seconds)
        self.simulations.add_event(
            models.SimulationEvent(
                id=new_id("simevt"),
                simulation_run_id=run.id,
                sim_time_s=request.sim_time_s,
                event_type="device_behavior_triggered",
                payload=published,
            )
        )
        snapshot.setdefault("frontend_events", []).append(published)
        return published

    def _process_runtime_emitted_events(
        self,
        run: models.SimulationRun,
        snapshot: dict[str, Any],
        emitted_events: list[dict[str, Any]],
        request: ActionCompleteRequest,
    ) -> dict[str, list[dict[str, Any]]]:
        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)

        followup_events: list[dict[str, Any]] = []
        followup_tasks: list[dict[str, Any]] = []
        followup_frontend_events: list[dict[str, Any]] = []
        for event in emitted_events:
            recorded = self._append_runtime_emitted_event(snapshot, event)
            followup_events.append(recorded)

            event_id = event.get("event_id")
            if event_id == "conveyor.stop_point_occupied":
                created = self._enqueue_next_stop_point_task(run, scene.current_document, snapshot, event, request)
                if created:
                    followup_tasks.append(created["task"])
                    if created.get("frontend_event"):
                        followup_frontend_events.append(created["frontend_event"])
            elif event_id in {"conveyor.stop_point_released", "conveyor.capacity_available"}:
                created = self._resume_waiting_conveyor_task(run, scene.current_document, snapshot, event, request)
                if created:
                    followup_tasks.append(created["task"])
                    if created.get("frontend_event"):
                        followup_frontend_events.append(created["frontend_event"])

        return {"events": followup_events, "device_tasks": followup_tasks, "frontend_events": followup_frontend_events}

    def _enqueue_next_stop_point_task(
        self,
        run: models.SimulationRun,
        scene_doc: dict[str, Any],
        snapshot: dict[str, Any],
        event: dict[str, Any],
        request: ActionCompleteRequest,
    ) -> dict[str, Any] | None:
        payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
        conveyor_id = payload.get("conveyor_id")
        point_id = payload.get("point_id")
        material_id = self._runtime_material_id(payload)
        if not conveyor_id or not point_id or not material_id:
            return None

        executor = ActionExecutor({}, snapshot)
        if executor._is_exit_stop_point(conveyor_id, point_id):
            return None
        next_point_id = executor._next_stop_point(conveyor_id, point_id)
        if not next_point_id:
            return None
        if executor._material_at_stop_point(conveyor_id, next_point_id):
            self._append_waiting_conveyor_item(run.id, snapshot, conveyor_id, material_id, point_id, payload)
            return None

        task_payload = self._strip_runtime_execution_fields(payload)
        task_payload.update(
            {
                "material_id": material_id,
                "from_point_id": point_id,
                "from_stop_point_id": point_id,
                "to_point_id": next_point_id,
                "to_stop_point_id": next_point_id,
            }
        )
        if payload.get("carrier_id"):
            task_payload["carrier_id"] = payload.get("carrier_id")
        if payload.get("transport_goal_behavior_id"):
            task_payload["transport_goal_behavior_id"] = payload.get("transport_goal_behavior_id")
        return self._enqueue_runtime_followup_task(
            run,
            scene_doc,
            snapshot,
            conveyor_id,
            "advance_to_next_stop_point",
            task_payload,
            request,
            trigger_signal=event.get("event_id"),
            route_id="runtime.stop_point_advance",
            created_by_event_id=event.get("event_id"),
        )

    def _resume_waiting_conveyor_task(
        self,
        run: models.SimulationRun,
        scene_doc: dict[str, Any],
        snapshot: dict[str, Any],
        event: dict[str, Any],
        request: ActionCompleteRequest,
    ) -> dict[str, Any] | None:
        conveyor_id = event.get("payload", {}).get("conveyor_id")
        if not conveyor_id:
            return None
        waiting = list(snapshot.setdefault("wait_queues", {}).get(f"conveyor:{conveyor_id}", []))
        if not waiting:
            return None

        executor = ActionExecutor({}, snapshot)
        for item in self._sort_waiting_conveyor_items(snapshot, conveyor_id, waiting):
            item_payload = deepcopy(item.get("payload", item)) if isinstance(item, dict) else {}
            material_id = self._runtime_material_id(item_payload) or item.get("material_id")
            point_id = item.get("waiting_at_point_id") or item_payload.get("from_point_id") or item.get("point_id") or executor._current_stop_point_for_material(conveyor_id, material_id)
            next_point_id = executor._next_stop_point(conveyor_id, point_id)
            if not material_id or not point_id or not next_point_id:
                continue
            if executor._material_at_stop_point(conveyor_id, next_point_id):
                continue

            task_payload = self._strip_runtime_execution_fields(item_payload)
            task_payload.update(
                {
                    "material_id": material_id,
                    "from_point_id": point_id,
                    "from_stop_point_id": point_id,
                    "to_point_id": next_point_id,
                    "to_stop_point_id": next_point_id,
                }
            )
            if item_payload.get("transport_goal_behavior_id"):
                task_payload["transport_goal_behavior_id"] = item_payload.get("transport_goal_behavior_id")
            created = self._enqueue_runtime_followup_task(
                run,
                scene_doc,
                snapshot,
                conveyor_id,
                item.get("behavior_id") or "advance_to_next_stop_point",
                task_payload,
                request,
                trigger_signal=event.get("event_id"),
                route_id="runtime.stop_point_resume",
                created_by_event_id=event.get("event_id"),
            )
            if created:
                self._remove_waiting_conveyor_item(snapshot, conveyor_id, material_id, point_id, task_id=item.get("task_id"))
                return created
        return None

    def _enqueue_runtime_followup_task(
        self,
        run: models.SimulationRun,
        scene_doc: dict[str, Any],
        snapshot: dict[str, Any],
        instance_id: str,
        behavior_id: str,
        task_payload: dict[str, Any],
        request: ActionCompleteRequest,
        *,
        trigger_signal: str | None,
        route_id: str,
        created_by_event_id: str | None,
    ) -> dict[str, Any] | None:
        instance = self._find_scene_instance(scene_doc, instance_id)
        if not instance:
            return None
        task_payload = DeviceRuntime._payload_with_instance_runtime_context(task_payload, instance)
        task_payload = ActionExecutor({}, snapshot).prepare_behavior_payload(instance_id, behavior_id, task_payload)
        task = {
            "task_id": new_id("task"),
            "run_id": run.id,
            "instance_id": instance_id,
            "device_type": instance.get("device_type"),
            "trigger_signal": trigger_signal,
            "signal_port": None,
            "behavior_id": behavior_id,
            "payload": task_payload,
            "status": "pending",
            "source_signal": trigger_signal,
            "route_id": route_id,
            "edge_id": None,
            "created_by_event_id": created_by_event_id,
        }
        self.runtime_store.enqueue_device_task(run.id, task, request.ttl_seconds)
        self.simulations.add_event(
            models.SimulationEvent(
                id=new_id("simevt"),
                simulation_run_id=run.id,
                sim_time_s=request.sim_time_s,
                event_type="device_task_created",
                payload=task,
            )
        )
        snapshot.setdefault("device_tasks", []).append(task)
        self._mark_device_queued(snapshot, instance_id)
        frontend_event = self._publish_frontend_behavior_event(run, task, request, snapshot)
        return {"task": task, "frontend_event": frontend_event}

    @staticmethod
    def _append_runtime_emitted_event(snapshot: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        recorded = {
            "event_id": new_id("evt"),
            "type": "behavior_graph_event",
            "signal_id": event.get("event_id"),
            "payload": deepcopy(event.get("payload", {})),
            "status": "delivered",
            "sim_time_s": event.get("sim_time_s"),
            "source": event.get("source", "action_executor"),
        }
        snapshot.setdefault("event_queue", []).append(recorded)
        return recorded

    @staticmethod
    def _prepare_task_for_frontend_runtime(snapshot: dict[str, Any], task: dict[str, Any]) -> None:
        instance_id = task.get("instance_id")
        behavior_id = task.get("behavior_id")
        if not instance_id or behavior_id not in CONVEYOR_BEHAVIORS:
            return
        task["payload"] = ActionExecutor({}, snapshot).prepare_behavior_payload(instance_id, behavior_id, task.get("payload", {}))

    @staticmethod
    def _apply_task_start_side_effects(snapshot: dict[str, Any], task: dict[str, Any]) -> None:
        instance_id = task.get("instance_id")
        behavior_id = task.get("behavior_id")
        if not instance_id or behavior_id not in CONVEYOR_BEHAVIORS or task.get("start_side_effects_applied"):
            return
        ActionExecutor({}, snapshot).apply_start_side_effects(instance_id, behavior_id, task.get("payload", {}))
        task["start_side_effects_applied"] = True

    @staticmethod
    def _should_emit_completion_signals(snapshot: dict[str, Any], completion_result: dict[str, Any]) -> bool:
        completed = SimulationService._completed_runtime_item(completion_result)
        if not completed:
            return False
        return completed.get("behavior_id") not in CONVEYOR_BEHAVIORS

    @staticmethod
    def _should_enqueue_process_handoffs(snapshot: dict[str, Any], completion_result: dict[str, Any]) -> bool:
        completed = SimulationService._completed_runtime_item(completion_result)
        if not completed:
            return False
        behavior_id = completed.get("behavior_id")
        if behavior_id not in CONVEYOR_BEHAVIORS:
            return True
        if behavior_id not in CONVEYOR_MOVE_BEHAVIORS:
            return False
        instance_id = completed.get("instance_id")
        to_point_id = completed.get("payload", {}).get("to_point_id") or completed.get("payload", {}).get("to_stop_point_id")
        return bool(instance_id and to_point_id and ActionExecutor({}, snapshot)._is_exit_stop_point(instance_id, to_point_id))

    @staticmethod
    def _release_completed_conveyor_exit_for_handoff(snapshot: dict[str, Any], completed: dict[str, Any], request: ActionCompleteRequest) -> None:
        behavior_id = completed.get("behavior_id")
        if behavior_id not in CONVEYOR_MOVE_BEHAVIORS:
            return
        instance_id = completed.get("instance_id")
        payload = completed.get("payload", {})
        point_id = payload.get("to_point_id") or payload.get("to_stop_point_id")
        if not instance_id or not point_id or not ActionExecutor({}, snapshot)._is_exit_stop_point(instance_id, point_id):
            return
        material_id = SimulationService._runtime_material_id(payload)
        if ActionExecutor({}, snapshot)._material_at_stop_point(instance_id, point_id) is None:
            return
        ActionExecutor({}, snapshot)._release_stop_point(instance_id, point_id, material_id, decrement_load=True)
        snapshot.setdefault("event_queue", []).append(
            {
                "event_id": new_id("evt"),
                "type": "behavior_graph_event",
                "signal_id": "conveyor.stop_point_released",
                "payload": {
                    "conveyor_id": instance_id,
                    "point_id": point_id,
                    "material_id": material_id,
                    "released_by": "process_handoff",
                },
                "status": "delivered",
                "sim_time_s": request.sim_time_s,
                "source": "process_handoff",
            }
        )

    @staticmethod
    def _append_waiting_conveyor_item(run_id: str, snapshot: dict[str, Any], conveyor_id: str, material_id: str, point_id: str, payload: dict[str, Any]) -> None:
        item = {
            "task_id": new_id("task"),
            "run_id": run_id,
            "instance_id": conveyor_id,
            "device_type": "conveyor",
            "behavior_id": "advance_to_next_stop_point",
            "payload": deepcopy(payload),
            "status": "waiting_conveyor",
            "waiting_for_conveyor": conveyor_id,
            "waiting_at_point_id": point_id,
        }
        waiting_material = {"material_id": material_id, "point_id": point_id, "task_id": item["task_id"]}
        wait_queue = snapshot.setdefault("wait_queues", {}).setdefault(f"conveyor:{conveyor_id}", [])
        if not any(SimulationService._waiting_conveyor_item_matches(entry, material_id, point_id, None) for entry in wait_queue):
            wait_queue.append(item)
        conveyor_queue = snapshot.setdefault("conveyor_queues", {}).setdefault(conveyor_id, {"queue_id": f"{conveyor_id}.stop_point_queue", "waiting_materials": []})
        if not any(entry.get("material_id") == material_id and entry.get("point_id") == point_id for entry in conveyor_queue.setdefault("waiting_materials", [])):
            conveyor_queue["waiting_materials"].append(waiting_material)

    @staticmethod
    def _remove_waiting_conveyor_item(snapshot: dict[str, Any], conveyor_id: str, material_id: str | None, point_id: str | None, *, task_id: str | None = None) -> None:
        queue_key = f"conveyor:{conveyor_id}"
        snapshot.setdefault("wait_queues", {})[queue_key] = [
            item
            for item in snapshot.setdefault("wait_queues", {}).get(queue_key, [])
            if not SimulationService._waiting_conveyor_item_matches(item, material_id, point_id, task_id)
        ]
        conveyor_queue = snapshot.setdefault("conveyor_queues", {}).setdefault(conveyor_id, {"queue_id": f"{conveyor_id}.stop_point_queue", "waiting_materials": []})
        conveyor_queue["waiting_materials"] = [
            item
            for item in conveyor_queue.get("waiting_materials", [])
            if not SimulationService._waiting_conveyor_item_matches(item, material_id, point_id, task_id)
        ]

    @staticmethod
    def _waiting_conveyor_item_matches(item: dict[str, Any], material_id: str | None, point_id: str | None, task_id: str | None) -> bool:
        if task_id and item.get("task_id") == task_id:
            return True
        payload = item.get("payload", {}) if isinstance(item.get("payload"), dict) else item
        item_material_id = SimulationService._runtime_material_id(payload) or item.get("material_id")
        item_point_id = item.get("waiting_at_point_id") or item.get("point_id") or payload.get("from_point_id")
        return item_material_id == material_id and (point_id is None or item_point_id == point_id)

    @staticmethod
    def _sort_waiting_conveyor_items(snapshot: dict[str, Any], conveyor_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ordered = ActionExecutor({}, snapshot)._ordered_stop_point_ids(conveyor_id)
        order = {point_id: index for index, point_id in enumerate(ordered)}
        return sorted(items, key=lambda item: order.get(item.get("waiting_at_point_id") or item.get("point_id") or item.get("payload", {}).get("from_point_id"), -1), reverse=True)

    @staticmethod
    def _runtime_material_id(payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        for key in ["material_id", "carrier_id", "subject_id", "workpiece_id", "object_id"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _complete_runtime_action(snapshot: dict[str, Any], action_ref: str, payload: ActionCompleteRequest) -> dict[str, Any]:
        active_actions = snapshot.setdefault("active_actions", {})
        if action_ref in active_actions:
            completed = ActionExecutor({}, snapshot).complete_action(action_ref, sim_time_s=payload.sim_time_s)
            SimulationService._mark_related_task_done(snapshot, action_ref, payload)
            SimulationService._mark_frontend_event_done(snapshot, action_ref, payload.status)
            events = [event for event in snapshot.get("event_queue", []) if event.get("action_id") == action_ref and event.get("type") == "device_action_completed"]
            return {"status": "completed_active_action", **completed, "events": events}

        task = SimulationService._find_device_task(snapshot, action_ref)
        if not task:
            return {"status": "not_found", "completed_action": None, "completed_task": None, "events": []}

        if task.get("status") in {"done", "failed", "visual_done"}:
            SimulationService._mark_frontend_event_done(snapshot, action_ref, str(task.get("status")))
            return {"status": "already_completed", "completed_action": None, "completed_task": task, "events": []}

        SimulationService._prepare_task_for_frontend_runtime(snapshot, task)
        SimulationService._apply_task_start_side_effects(snapshot, task)
        task["status"] = payload.status
        task["completed_at_sim_time_s"] = payload.sim_time_s
        task["completion_payload"] = deepcopy(payload.payload)
        instance_id = task.get("instance_id")
        if instance_id:
            snapshot.setdefault("device_states", {})[instance_id] = "idle" if payload.status == "done" else "failed"
            snapshot.setdefault("device_fsm_states", {})[instance_id] = "idle" if payload.status == "done" else "failed"

        event = {
            "event_id": new_id("evt"),
            "type": "device_action_completed",
            "task_id": task.get("task_id"),
            "action_id": task.get("action_id"),
            "instance_id": instance_id,
            "behavior_id": task.get("behavior_id"),
            "payload": deepcopy(task.get("payload", {})),
            "completion_payload": deepcopy(payload.payload),
            "status": payload.status,
            "sim_time_s": payload.sim_time_s,
            "completed_by": "frontend_runtime",
        }
        completed = ActionExecutor({}, snapshot).complete_task(task, sim_time_s=payload.sim_time_s)
        snapshot.setdefault("event_queue", []).append(event)
        SimulationService._mark_frontend_event_done(snapshot, action_ref, payload.status)
        return {"status": "completed_device_task", "completed_action": None, **completed, "events": [event]}

    @staticmethod
    def _find_device_task(snapshot: dict[str, Any], action_ref: str) -> dict[str, Any] | None:
        for task in snapshot.setdefault("device_tasks", []):
            if action_ref in {task.get("task_id"), task.get("action_id")}:
                return task
        return None

    @staticmethod
    def _mark_related_task_done(snapshot: dict[str, Any], action_ref: str, payload: ActionCompleteRequest) -> None:
        for task in snapshot.setdefault("device_tasks", []):
            if action_ref in {task.get("task_id"), task.get("action_id")}:
                task["status"] = payload.status
                task["completed_at_sim_time_s"] = payload.sim_time_s
                task["completion_payload"] = deepcopy(payload.payload)

    @staticmethod
    def _mark_frontend_event_done(snapshot: dict[str, Any], action_ref: str, status: str) -> None:
        for event in snapshot.setdefault("frontend_events", []):
            if action_ref in {event.get("task_id"), event.get("action_id"), event.get("event_id")}:
                event["status"] = status

    # 生成初始快照：根据场景文档创建仿真启动时的默认运行状态。
    @staticmethod
    def _initial_snapshot(scene: models.Scene) -> dict[str, Any]:
        document = scene.current_document
        conveyor_runtime = SimulationService._initial_conveyor_runtime_state(document)
        return {
            "schema_type": "RuntimeSnapshot",
            "version": "0.2.0",
            "run_id": None,
            "clock": 0,
            "topology_graph_ref": document.get("derived_artifacts", {}).get("topology_graph", {}),
            "signal_values": {},
            "event_queue": [],
            "frontend_events": [],
            "device_tasks": [],
            "device_states": {instance.get("instance_id"): "idle" for instance in document.get("instances", [])},
            "device_fsm_states": {instance.get("instance_id"): "idle" for instance in document.get("instances", [])},
            "material_locations": {item.get("material_id"): item.get("located_at") for item in document.get("materials", [])},
            "resource_locks": {},
            "active_actions": {},
            **conveyor_runtime,
        }

    @staticmethod
    def _initial_conveyor_runtime_state(document: dict[str, Any]) -> dict[str, Any]:
        stop_points: dict[str, dict[str, Any]] = {}
        occupancy: dict[str, dict[str, Any]] = {}
        queues: dict[str, dict[str, Any]] = {}
        loads: dict[str, dict[str, Any]] = {}

        for instance in document.get("instances", []):
            if instance.get("device_type") != "conveyor":
                continue
            instance_id = instance.get("instance_id")
            if not instance_id:
                continue
            points = SimulationService._runtime_stop_points_for_instance(instance)
            if points:
                stop_points[instance_id] = {"generation": "scene_document_runtime_geometry", "points": points}
                occupancy[instance_id] = {point["point_id"]: None for point in points}
            params = instance.get("param_overrides", {}) if isinstance(instance.get("param_overrides"), dict) else {}
            max_capacity = params.get("max_capacity", params.get("capacity", max(1, len(points) or 1)))
            resume_threshold = params.get("resume_threshold", max_capacity)
            loads[instance_id] = {
                "current_load": 0,
                "max_capacity": int(max_capacity),
                "resume_threshold": int(resume_threshold),
                "blocked": False,
            }
            queues[instance_id] = {"queue_id": f"{instance_id}.stop_point_queue", "waiting_materials": []}

        return {
            "conveyor_stop_points": stop_points,
            "conveyor_occupancy": occupancy,
            "conveyor_queues": queues,
            "conveyor_loads": loads,
            "wait_queues": {},
        }

    @staticmethod
    def _runtime_stop_points_for_instance(instance: dict[str, Any]) -> list[dict[str, Any]]:
        transport_path = (
            instance.get("runtime_geometry", {}).get("transport_path", {})
            if isinstance(instance.get("runtime_geometry"), dict)
            else {}
        )
        raw_points = transport_path.get("stop_points", []) if isinstance(transport_path, dict) else []
        points: list[dict[str, Any]] = []
        for index, point in enumerate(raw_points if isinstance(raw_points, list) else []):
            if not isinstance(point, dict):
                continue
            point_id = point.get("point_id") or point.get("id")
            if not point_id:
                continue
            points.append(
                {
                    "point_id": point_id,
                    "index": int(point.get("index", index)),
                    "t": point.get("t"),
                    "role": point.get("role", "middle"),
                    "position": deepcopy(point.get("position")),
                    "coordinate_source": "SceneDocument.instances.runtime_geometry.transport_path.stop_points",
                }
            )
        if points:
            return sorted(points, key=lambda item: item.get("index", 0))

        start = transport_path.get("start_position") if isinstance(transport_path, dict) else None
        end = transport_path.get("end_position") if isinstance(transport_path, dict) else None
        params = instance.get("param_overrides", {}) if isinstance(instance.get("param_overrides"), dict) else {}
        count = int(params.get("stop_point_count", 0) or 0)
        if not (isinstance(start, list) and isinstance(end, list) and len(start) >= 3 and len(end) >= 3 and count >= 2):
            return []
        generated: list[dict[str, Any]] = []
        for index in range(count):
            t = index / (count - 1)
            generated.append(
                {
                    "point_id": f"{instance.get('instance_id')}.sp_{index + 1:02d}",
                    "index": index,
                    "t": round(t, 4),
                    "role": "entry" if index == 0 else "exit" if index == count - 1 else "middle",
                    "position": [float(start[axis]) + (float(end[axis]) - float(start[axis])) * t for axis in range(3)],
                    "coordinate_source": "SceneDocument.instances.runtime_geometry.transport_path.start_end_interpolation",
                }
            )
        return generated
