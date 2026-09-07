from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db import models
from app.repositories.sql import DeviceSpecRepository, SceneRepository, SimulationRepository
from app.schemas.domain import SignalEmitRequest
from app.services.device_runtime import DeviceRuntime
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore


class SignalBusRuntime:
    """Minimal runtime signal router for Phase 1.

    This class mirrors VC's signal delivery boundary without executing device
    behavior yet: a source signal is recorded, enabled SceneDocument signal
    edges are routed, and target device inputs become pending device tasks.
    """

    # 初始化信号总线运行时：注入数据库会话、各类仓储和运行时状态存储。
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.scenes = SceneRepository(db)
        self.simulations = SimulationRepository(db)
        self.device_specs = DeviceSpecRepository(db)
        self.runtime_store = runtime_store

    # 发出信号并执行路由：记录源信号，匹配场景中的 signal_edges，生成路由事件和设备任务。
    def emit(self, run: models.SimulationRun, signal_id: str, payload: SignalEmitRequest) -> dict[str, Any]:
        # 先根据仿真运行绑定的 scene_id 找到场景，找不到则说明运行数据异常。
        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)

        # 记录本次信号发出前的旧信号状态，用于判断 rising/falling/change 等触发条件。
        previous_signals = deepcopy(self.runtime_store.get_signals(run.id))

        # 把当前源信号写入运行时状态和数据库事件表。
        source_event = self._record_signal(
            run,
            signal_id,
            payload.value,
            payload.payload,
            payload,
            "signal_event",
            {"delivery": "source_emit"},
        )

        # 取出当前运行快照，并把源信号值和事件追加进去。
        snapshot = self._snapshot_for_run(run)
        self._apply_signal_to_snapshot(snapshot, signal_id, payload.value)
        self._append_snapshot_event(snapshot, {"type": "signal_event", **source_event})

        # 分别收集成功路由的事件、创建出的设备任务，以及被跳过的路由原因。
        routed_events: list[dict[str, Any]] = []
        device_tasks: list[dict[str, Any]] = []
        frontend_events: list[dict[str, Any]] = []
        skipped_routes: list[dict[str, Any]] = []
        route_edges, route_source = self._signal_routes_for_run(scene, run)
        route_index = self._signal_route_index(route_edges)
        device_runtime = DeviceRuntime(self.device_specs)

        # 遍历当前路由源中的信号边，只有 source 匹配当前 signal_id 且启用的边才会参与路由。
        for edge in route_index.get(signal_id, []):
            if edge.get("enabled", True) is False:
                continue
            if edge.get("status", "valid") == "invalid":
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "reason": "invalid_topology_edge",
                        "route_source": route_source,
                    }
                )
                continue

            # 根据边上的 trigger 配置判断是否触发；不满足则记录跳过原因。
            if not self._trigger_matches(edge.get("trigger", "on_rising_edge"), previous_signals.get(signal_id), payload.value):
                skipped_routes.append(
                    {
                    "edge_id": edge.get("edge_id"),
                    "route_id": edge.get("route_id"),
                    "route_source": route_source,
                    "reason": "trigger_not_matched",
                }
                )
                continue

            # 对信号值和 payload 做转换；当前只支持 identity，其他类型会被跳过。
            transformed = self._apply_transform(edge.get("transform", {"type": "identity"}), payload.value, payload.payload)
            if transformed is None:
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "route_source": route_source,
                        "reason": "unsupported_transform",
                        "transform": edge.get("transform"),
                    }
                )
                continue

            # 边必须有目标信号 target，没有 target 就无法继续路由。
            target_signal = edge.get("target")
            if not target_signal:
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "route_source": route_source,
                        "reason": "missing_target_signal",
                    }
                )
                continue

            # 记录目标信号事件，表示源信号已经通过这条边路由到了目标端。
            routed_event = self._record_signal(
                run,
                target_signal,
                transformed["value"],
                transformed["payload"],
                payload,
                "routed_signal_event",
                {
                    "source_signal": signal_id,
                    "target_signal": target_signal,
                    "edge_id": edge.get("edge_id"),
                    "route_id": edge.get("route_id"),
                    "delivery": edge.get("delivery"),
                    "trigger": edge.get("trigger"),
                    "transform": edge.get("transform", {"type": "identity"}),
                    "route_source": route_source,
                },
            )
            routed_events.append(routed_event)

            # 同步更新快照里的目标信号值和事件队列。
            self._apply_signal_to_snapshot(snapshot, target_signal, transformed["value"])
            self._append_snapshot_event(snapshot, {"type": "routed_signal_event", **routed_event})

            # 如果目标信号能对应到设备输入，则生成一个等待执行的设备任务。
            task = device_runtime.on_signal(run, scene.current_document, target_signal, transformed["payload"], edge, routed_event)
            if task:
                self.runtime_store.enqueue_device_task(run.id, task, payload.ttl_seconds)
                self._record_db_event(run, payload, "device_task_created", task)
                self._append_snapshot_task(snapshot, task)
                self._mark_device_queued(snapshot, task["instance_id"])
                device_tasks.append(task)
                frontend_event = self._publish_frontend_behavior_event(run, task, payload, snapshot)
                if frontend_event:
                    frontend_events.append(frontend_event)

        # 保存更新后的运行快照，同时同步到数据库模型对象，等待外层提交事务。
        self.runtime_store.put_snapshot(run.id, snapshot, payload.ttl_seconds)
        run.runtime_snapshot = snapshot

        # 返回本次信号发出后的完整处理结果，便于 API 层直接响应调用方。
        return {
            "signal_id": signal_id,
            "value": payload.value,
            "payload": payload.payload,
            "source_event": source_event,
            "routed_events": routed_events,
            "device_tasks": device_tasks,
            "frontend_events": frontend_events,
            "skipped_routes": skipped_routes,
            "route_source": route_source,
            "event_queue_count": len(snapshot.get("event_queue", [])),
        }

    def get_signal_consumers(self, run: models.SimulationRun, source_signal: str) -> list[dict[str, Any]]:
        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)
        route_edges, _ = self._signal_routes_for_run(scene, run)
        return self._signal_route_index(route_edges).get(source_signal, [])

    def _signal_routes_for_run(self, scene: models.Scene, run: models.SimulationRun) -> tuple[list[dict[str, Any]], str]:
        topology = self.scenes.latest_topology(scene.id)
        if topology and topology.scene_revision == run.base_scene_revision:
            return topology.document.get("signal_graph", {}).get("edges", []), "topology_graph"
        return scene.current_document.get("signal_edges", []), "scene_document"

    @staticmethod
    def _signal_route_index(edges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for edge in edges:
            source = edge.get("source")
            if source:
                index.setdefault(source, []).append(edge)
        return index

    # 记录信号事件：写入运行时信号状态，并同步创建一条数据库事件。
    def _record_signal(
        self,
        run: models.SimulationRun,
        signal_id: str,
        value: Any,
        event_payload: dict[str, Any],
        request: SignalEmitRequest,
        event_type: str,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        event = self.runtime_store.set_signal(
            run.id,
            signal_id,
            value,
            event_payload,
            request.ttl_seconds,
            event_type=event_type,
            event_metadata={"event_id": new_id("sigevt"), **metadata},
        )
        self._record_db_event(run, request, event_type, event)
        return event

    # 写入数据库事件：把仿真运行中的信号/任务事件保存到 SimulationEvent 表。
    def _record_db_event(
        self,
        run: models.SimulationRun,
        request: SignalEmitRequest,
        event_type: str,
        event_payload: dict[str, Any],
    ) -> None:
        self.simulations.add_event(
            models.SimulationEvent(
                id=new_id("simevt"),
                simulation_run_id=run.id,
                sim_time_s=request.sim_time_s,
                event_type=event_type,
                payload=event_payload,
            )
        )

    # 获取运行快照：优先读取 runtime_store，没有则回退到数据库记录里的 runtime_snapshot。
    def _snapshot_for_run(self, run: models.SimulationRun) -> dict[str, Any]:
        snapshot = self.runtime_store.get_snapshot(run.id) or run.runtime_snapshot or {}
        return deepcopy(snapshot)

    # 更新快照信号值：把某个 signal_id 的最新值写入 snapshot.signal_values。
    @staticmethod
    def _apply_signal_to_snapshot(snapshot: dict[str, Any], signal_id: str, value: Any) -> None:
        snapshot.setdefault("signal_values", {})[signal_id] = value

    # 追加快照事件：把已投递的信号事件放入 snapshot.event_queue。
    @staticmethod
    def _append_snapshot_event(snapshot: dict[str, Any], event: dict[str, Any]) -> None:
        snapshot.setdefault("event_queue", []).append(
            {
                "event_id": event.get("event_id") or new_id("sigevt"),
                "source_signal": event.get("source_signal") or event.get("signal_id"),
                "target_signal": event.get("target_signal"),
                "signal_id": event.get("signal_id"),
                "payload": event.get("payload", {}),
                "value": event.get("value"),
                "delivery": event.get("delivery", "event"),
                "status": "delivered",
                "type": event.get("type"),
                "route_id": event.get("route_id"),
                "edge_id": event.get("edge_id"),
            }
        )

    # 追加设备任务：把待执行的设备任务放入 snapshot.device_tasks。
    @staticmethod
    def _append_snapshot_task(snapshot: dict[str, Any], task: dict[str, Any]) -> None:
        snapshot.setdefault("device_tasks", []).append(task)

    # 追加前端事件：把可播放行为事件放入 snapshot.frontend_events，方便调试和快照回放。
    @staticmethod
    def _append_snapshot_frontend_event(snapshot: dict[str, Any], event: dict[str, Any]) -> None:
        snapshot.setdefault("frontend_events", []).append(event)

    # 标记设备排队：当设备当前为空闲状态时，把设备状态更新为 queued。
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
        request: SignalEmitRequest,
        snapshot: dict[str, Any],
    ) -> dict[str, Any] | None:
        behavior_id = task.get("behavior_id")
        if not behavior_id:
            return None

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
        self._record_db_event(run, request, "device_behavior_triggered", published)
        self._append_snapshot_frontend_event(snapshot, published)
        return published

    # 判断触发条件：根据旧值和新值判断 manual/level/on_change/falling/rising 是否满足。
    @staticmethod
    def _trigger_matches(trigger: str, previous_event: dict[str, Any] | None, value: Any) -> bool:
        previous_value = previous_event.get("value") if previous_event else None
        if trigger == "manual":
            return True
        if trigger == "level":
            return bool(value)
        if trigger == "on_change":
            return previous_event is None or previous_value != value
        if trigger == "on_falling_edge":
            return bool(previous_value) and not bool(value)
        return not bool(previous_value) and bool(value)

    # 应用信号转换：根据 transform 配置转换 value/payload，当前仅支持 identity 原样传递。
    @staticmethod
    def _apply_transform(transform: dict[str, Any], value: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        transform_type = transform.get("type", "identity") if isinstance(transform, dict) else "identity"
        if transform_type == "identity":
            return {"value": value, "payload": deepcopy(payload)}
        return None

    # 生成设备任务：根据目标信号定位设备实例和行为，组装 pending 状态的任务对象。
    def _device_task_for_target(
        self,
        run: models.SimulationRun,
        scene_doc: dict[str, Any],
        target_signal: str,
        payload: dict[str, Any],
        edge: dict[str, Any],
        routed_event: dict[str, Any],
    ) -> dict[str, Any] | None:
        # 目标信号格式必须是 instance_id.signal_port，无法解析则不创建任务。
        parsed = self._parse_signal_ref(target_signal)
        if not parsed:
            return None
        instance_id, signal_port = parsed

        # 从场景文档里找到目标设备实例，找不到也不创建任务。
        instance = self._find_instance(scene_doc, instance_id)
        if not instance:
            return None

        # 根据实例关联的设备规格，推断该信号应该触发哪个设备行为。
        spec = self.device_specs.get(instance.get("spec_id", ""))
        spec_doc = spec.document if spec else {}
        behavior_id = self._behavior_for_signal(spec_doc, signal_port)

        return {
            "task_id": new_id("task"),
            "run_id": run.id,
            "instance_id": instance_id,
            "device_type": instance.get("device_type"),
            "trigger_signal": target_signal,
            "signal_port": signal_port,
            "behavior_id": behavior_id,
            "payload": deepcopy(payload),
            "status": "pending",
            "source_signal": edge.get("source"),
            "route_id": edge.get("route_id"),
            "edge_id": edge.get("edge_id"),
            "created_by_event_id": routed_event.get("event_id"),
        }

    # 解析信号引用：把 instance_id.signal_port 拆成实例 ID 和信号端口名。
    @staticmethod
    def _parse_signal_ref(signal_ref: str) -> tuple[str, str] | None:
        if "." not in signal_ref:
            return None
        instance_id, signal_port = signal_ref.split(".", 1)
        if not instance_id or not signal_port:
            return None
        return instance_id, signal_port

    # 查找设备实例：在场景文档 instances 中按 instance_id 找到对应实例。
    @staticmethod
    def _find_instance(scene_doc: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
        for instance in scene_doc.get("instances", []):
            if instance.get("instance_id") == instance_id:
                return instance
        return None

    # 匹配设备行为：根据设备规格判断某个输入信号端口会触发哪个 transport_behavior。
    @staticmethod
    def _behavior_for_signal(spec_doc: dict[str, Any], signal_port: str) -> str | None:
        # 优先直接从行为定义中的 input_signals/control_signals 匹配。
        for behavior in spec_doc.get("transport_behaviors", []):
            if signal_port in behavior.get("input_signals", []) or signal_port in behavior.get("control_signals", []):
                return behavior.get("behavior_id")

        # 如果行为上没有直接声明，则通过 interface_bindings 间接找到绑定的行为。
        behavior_by_id = {
            behavior.get("behavior_id"): behavior
            for behavior in spec_doc.get("transport_behaviors", [])
            if behavior.get("behavior_id")
        }
        for binding in spec_doc.get("interface_bindings", []):
            if signal_port not in binding.get("signal_ports", []):
                continue
            for behavior_id in binding.get("transport_behaviors", []):
                if behavior_id in behavior_by_id:
                    return behavior_id
            return next(iter(binding.get("transport_behaviors", [])), None)
        return None
