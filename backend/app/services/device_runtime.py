from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.db import models
from app.repositories.sql import DeviceSpecRepository
from app.services.ids import new_id
from app.services.runtime_handlers import RuntimeHandlerRegistry


class DeviceRuntime:
    """Device-level runtime boundary, analogous to VC's controlled OnSignal layer."""

    def __init__(self, device_specs: DeviceSpecRepository, registry: RuntimeHandlerRegistry | None = None) -> None:
        self.device_specs = device_specs
        self.registry = registry or RuntimeHandlerRegistry()

    def on_signal(
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
        behavior_id = self.registry.resolve_behavior(instance.get("device_type"), spec_doc, signal_port)

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

    def dispatch_pending_tasks(
        self,
        snapshot: dict[str, Any],
        *,
        task_ids: list[str] | None = None,
        sim_time_s: float | None = None,
    ) -> dict[str, Any]:
        consumed_events = self.consume_routed_events(snapshot)
        selected = set(task_ids or [])
        dispatched: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []

        for task in snapshot.get("device_tasks", []):
            if selected and task.get("task_id") not in selected:
                continue
            if task.get("status") != "pending":
                skipped.append({"task_id": task.get("task_id"), "reason": "not_pending", "status": task.get("status")})
                continue
            if not task.get("behavior_id"):
                skipped.append({"task_id": task.get("task_id"), "reason": "missing_behavior_id"})
                continue

            action = self.registry.build_active_action(task, sim_time_s=sim_time_s)
            task["status"] = "running"
            task["action_id"] = action["action_id"]
            task["started_at_sim_time_s"] = sim_time_s
            snapshot.setdefault("active_actions", {})[action["action_id"]] = action
            self._mark_device_busy(snapshot, task["instance_id"])
            snapshot.setdefault("event_queue", []).append(
                {
                    "event_id": new_id("evt"),
                    "type": "device_action_started",
                    "task_id": task.get("task_id"),
                    "action_id": action["action_id"],
                    "instance_id": task.get("instance_id"),
                    "behavior_id": task.get("behavior_id"),
                    "payload": deepcopy(task.get("payload", {})),
                    "status": "running",
                    "sim_time_s": sim_time_s,
                }
            )
            dispatched.append(action)

        return {"consumed_events": consumed_events, "dispatched_actions": dispatched, "skipped_tasks": skipped}

    @staticmethod
    def consume_routed_events(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        task_event_ids = {task.get("created_by_event_id") for task in snapshot.get("device_tasks", []) if task.get("created_by_event_id")}
        consumed: list[dict[str, Any]] = []
        for event in snapshot.get("event_queue", []):
            if event.get("type") != "routed_signal_event" or event.get("status") != "delivered":
                continue
            if event.get("event_id") not in task_event_ids:
                continue
            event["status"] = "consumed"
            event["consumed_by"] = "DeviceRuntime"
            consumed.append(event)
        return consumed

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
    def _mark_device_busy(snapshot: dict[str, Any], instance_id: str) -> None:
        snapshot.setdefault("device_states", {})[instance_id] = "busy"
        snapshot.setdefault("device_fsm_states", {})[instance_id] = "busy"
