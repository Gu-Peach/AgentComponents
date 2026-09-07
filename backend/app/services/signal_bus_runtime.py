from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db import models
from app.repositories.sql import DeviceSpecRepository, SceneRepository, SimulationRepository
from app.schemas.domain import SignalEmitRequest
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore


class SignalBusRuntime:
    """Minimal runtime signal router for Phase 1.

    This class mirrors VC's signal delivery boundary without executing device
    behavior yet: a source signal is recorded, enabled SceneDocument signal
    edges are routed, and target device inputs become pending device tasks.
    """

    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.scenes = SceneRepository(db)
        self.simulations = SimulationRepository(db)
        self.device_specs = DeviceSpecRepository(db)
        self.runtime_store = runtime_store

    def emit(self, run: models.SimulationRun, signal_id: str, payload: SignalEmitRequest) -> dict[str, Any]:
        scene = self.scenes.get(run.scene_id)
        if not scene:
            raise NotFoundError("Scene", run.scene_id)

        previous_signals = deepcopy(self.runtime_store.get_signals(run.id))
        source_event = self._record_signal(
            run,
            signal_id,
            payload.value,
            payload.payload,
            payload,
            "signal_event",
            {"delivery": "source_emit"},
        )

        snapshot = self._snapshot_for_run(run)
        self._apply_signal_to_snapshot(snapshot, signal_id, payload.value)
        self._append_snapshot_event(snapshot, {"type": "signal_event", **source_event})

        routed_events: list[dict[str, Any]] = []
        device_tasks: list[dict[str, Any]] = []
        skipped_routes: list[dict[str, Any]] = []

        for edge in scene.current_document.get("signal_edges", []):
            if edge.get("source") != signal_id or edge.get("enabled", True) is False:
                continue
            if not self._trigger_matches(edge.get("trigger", "on_rising_edge"), previous_signals.get(signal_id), payload.value):
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "reason": "trigger_not_matched",
                    }
                )
                continue

            transformed = self._apply_transform(edge.get("transform", {"type": "identity"}), payload.value, payload.payload)
            if transformed is None:
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "reason": "unsupported_transform",
                        "transform": edge.get("transform"),
                    }
                )
                continue

            target_signal = edge.get("target")
            if not target_signal:
                skipped_routes.append(
                    {
                        "edge_id": edge.get("edge_id"),
                        "route_id": edge.get("route_id"),
                        "reason": "missing_target_signal",
                    }
                )
                continue

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
                },
            )
            routed_events.append(routed_event)
            self._apply_signal_to_snapshot(snapshot, target_signal, transformed["value"])
            self._append_snapshot_event(snapshot, {"type": "routed_signal_event", **routed_event})

            task = self._device_task_for_target(run, scene.current_document, target_signal, transformed["payload"], edge, routed_event)
            if task:
                self.runtime_store.enqueue_device_task(run.id, task, payload.ttl_seconds)
                self._record_db_event(run, payload, "device_task_created", task)
                self._append_snapshot_task(snapshot, task)
                self._mark_device_queued(snapshot, task["instance_id"])
                device_tasks.append(task)

        self.runtime_store.put_snapshot(run.id, snapshot, payload.ttl_seconds)
        run.runtime_snapshot = snapshot

        return {
            "signal_id": signal_id,
            "value": payload.value,
            "payload": payload.payload,
            "source_event": source_event,
            "routed_events": routed_events,
            "device_tasks": device_tasks,
            "skipped_routes": skipped_routes,
            "event_queue_count": len(snapshot.get("event_queue", [])),
        }

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

    def _snapshot_for_run(self, run: models.SimulationRun) -> dict[str, Any]:
        snapshot = self.runtime_store.get_snapshot(run.id) or run.runtime_snapshot or {}
        return deepcopy(snapshot)

    @staticmethod
    def _apply_signal_to_snapshot(snapshot: dict[str, Any], signal_id: str, value: Any) -> None:
        snapshot.setdefault("signal_values", {})[signal_id] = value

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

    @staticmethod
    def _append_snapshot_task(snapshot: dict[str, Any], task: dict[str, Any]) -> None:
        snapshot.setdefault("device_tasks", []).append(task)

    @staticmethod
    def _mark_device_queued(snapshot: dict[str, Any], instance_id: str) -> None:
        device_states = snapshot.setdefault("device_states", {})
        if device_states.get(instance_id) in {None, "idle"}:
            device_states[instance_id] = "queued"
        fsm_states = snapshot.setdefault("device_fsm_states", {})
        if fsm_states.get(instance_id) in {None, "idle"}:
            fsm_states[instance_id] = "queued"

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

    @staticmethod
    def _apply_transform(transform: dict[str, Any], value: Any, payload: dict[str, Any]) -> dict[str, Any] | None:
        transform_type = transform.get("type", "identity") if isinstance(transform, dict) else "identity"
        if transform_type == "identity":
            return {"value": value, "payload": deepcopy(payload)}
        return None

    def _device_task_for_target(
        self,
        run: models.SimulationRun,
        scene_doc: dict[str, Any],
        target_signal: str,
        payload: dict[str, Any],
        edge: dict[str, Any],
        routed_event: dict[str, Any],
    ) -> dict[str, Any] | None:
        parsed = self._parse_signal_ref(target_signal)
        if not parsed:
            return None
        instance_id, signal_port = parsed
        instance = self._find_instance(scene_doc, instance_id)
        if not instance:
            return None
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

    @staticmethod
    def _parse_signal_ref(signal_ref: str) -> tuple[str, str] | None:
        if "." not in signal_ref:
            return None
        instance_id, signal_port = signal_ref.split(".", 1)
        if not instance_id or not signal_port:
            return None
        return instance_id, signal_port

    @staticmethod
    def _find_instance(scene_doc: dict[str, Any], instance_id: str) -> dict[str, Any] | None:
        for instance in scene_doc.get("instances", []):
            if instance.get("instance_id") == instance_id:
                return instance
        return None

    @staticmethod
    def _behavior_for_signal(spec_doc: dict[str, Any], signal_port: str) -> str | None:
        for behavior in spec_doc.get("transport_behaviors", []):
            if signal_port in behavior.get("input_signals", []) or signal_port in behavior.get("control_signals", []):
                return behavior.get("behavior_id")

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
