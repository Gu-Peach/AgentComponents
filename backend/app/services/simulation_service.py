from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.db import models
from app.repositories.sql import DeviceSpecRepository, ProjectRepository, SceneRepository, SimulationRepository
from app.schemas.domain import ActionCompleteRequest, DeviceTaskDispatchRequest, RuntimeSnapshotPut, SignalEmitRequest, SimulationRunCreate
from app.services.action_executor import ActionExecutor
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

        self.runtime_store.put_snapshot(run_id, snapshot, payload.ttl_seconds)
        run.runtime_snapshot = snapshot
        for event in result.get("events", []):
            self.simulations.add_event(
                models.SimulationEvent(
                    id=new_id("simevt"),
                    simulation_run_id=run.id,
                    sim_time_s=payload.sim_time_s,
                    event_type=event.get("type", "device_action_completed"),
                    payload=event,
                )
            )
        self.db.commit()
        return {"run_id": run_id, "action_ref": action_ref, **result, "snapshot": snapshot}

    # 清空运行时状态：确认仿真运行存在后，删除该 run_id 对应的临时运行数据。
    def clear_runtime_state(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        self.runtime_store.clear_run(run_id)
        return {"run_id": run_id, "cleared": True}

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
        snapshot.setdefault("event_queue", []).append(event)
        SimulationService._mark_frontend_event_done(snapshot, action_ref, payload.status)
        return {"status": "completed_device_task", "completed_action": None, "completed_task": task, "events": [event]}

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
        return {
            "schema_type": "RuntimeSnapshot",
            "version": "0.2.0",
            "run_id": None,
            "clock": 0,
            "topology_graph_ref": document.get("derived_artifacts", {}).get("topology_graph", {}),
            "signal_values": {},
            "event_queue": [],
            "device_states": {instance.get("instance_id"): "idle" for instance in document.get("instances", [])},
            "material_locations": {item.get("material_id"): item.get("located_at") for item in document.get("materials", [])},
            "resource_locks": {},
            "active_actions": {},
        }
