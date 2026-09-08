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
        task_payload = self._payload_with_instance_runtime_context(payload, instance)

        return {
            "task_id": new_id("task"),
            "run_id": run.id,
            "instance_id": instance_id,
            "device_type": instance.get("device_type"),
            "trigger_signal": target_signal,
            "signal_port": signal_port,
            "behavior_id": behavior_id,
            "payload": task_payload,
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
    def _payload_with_instance_runtime_context(payload: dict[str, Any], instance: dict[str, Any]) -> dict[str, Any]:
        enriched = deepcopy(payload)

        for key, value in (instance.get("param_overrides") or {}).items():
            enriched.setdefault(key, deepcopy(value))

        runtime_geometry = instance.get("runtime_geometry")
        runtime_kinematics = instance.get("runtime_kinematics")
        if runtime_geometry:
            enriched.setdefault("runtime_geometry", deepcopy(runtime_geometry))
            DeviceRuntime._apply_runtime_geometry_defaults(enriched, runtime_geometry)
        if runtime_kinematics:
            enriched.setdefault("runtime_kinematics", deepcopy(runtime_kinematics))

        if runtime_geometry or runtime_kinematics:
            enriched.setdefault(
                "scene_instance",
                {
                    "instance_id": instance.get("instance_id"),
                    "spec_id": instance.get("spec_id"),
                    "device_type": instance.get("device_type"),
                    "transform": deepcopy(instance.get("transform", {})),
                    "asset_binding": deepcopy(instance.get("asset_binding", {})),
                },
            )

        return enriched

    @staticmethod
    def _apply_runtime_geometry_defaults(payload: dict[str, Any], runtime_geometry: dict[str, Any]) -> None:
        transport_path = runtime_geometry.get("transport_path") if isinstance(runtime_geometry, dict) else None
        if isinstance(transport_path, dict):
            start_position = transport_path.get("start_position")
            end_position = transport_path.get("end_position")
            DeviceRuntime._setdefault_if_present(payload, "from_position", start_position)
            DeviceRuntime._setdefault_if_present(payload, "to_position", end_position)
            waypoints = transport_path.get("waypoints") or ([start_position, end_position] if start_position and end_position else None)
            if waypoints:
                payload.setdefault("waypoints", deepcopy(waypoints))

        pick_place_path = runtime_geometry.get("pick_place_path") if isinstance(runtime_geometry, dict) else None
        if isinstance(pick_place_path, dict):
            pick_position = pick_place_path.get("pick_position")
            place_position = pick_place_path.get("place_position")
            DeviceRuntime._setdefault_if_present(payload, "pick_position", pick_position)
            DeviceRuntime._setdefault_if_present(payload, "place_position", place_position)
            DeviceRuntime._setdefault_if_present(payload, "from_position", pick_position)
            DeviceRuntime._setdefault_if_present(payload, "to_position", place_position)
            DeviceRuntime._setdefault_if_present(payload, "input_process_port", pick_place_path.get("input_process_port"))
            DeviceRuntime._setdefault_if_present(payload, "output_process_port", pick_place_path.get("output_process_port"))
            lift_height = pick_place_path.get("lift_height") or pick_place_path.get("approach_height")
            if lift_height is not None:
                payload.setdefault("lift_height", lift_height)
            if pick_place_path.get("waypoints"):
                payload.setdefault("waypoints", deepcopy(pick_place_path["waypoints"]))

    @staticmethod
    def _setdefault_if_present(payload: dict[str, Any], key: str, value: Any) -> None:
        if value is not None:
            payload.setdefault(key, deepcopy(value))

    @staticmethod
    def _mark_device_busy(snapshot: dict[str, Any], instance_id: str) -> None:
        snapshot.setdefault("device_states", {})[instance_id] = "busy"
        snapshot.setdefault("device_fsm_states", {})[instance_id] = "busy"
