from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.ids import new_id


class DefaultDeviceHandler:
    """Resolve runtime behavior from DeviceSpec signal bindings."""

    def resolve_behavior(self, spec_doc: dict[str, Any], signal_port: str) -> str | None:
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

    def build_active_action(self, task: dict[str, Any], *, sim_time_s: float | None = None) -> dict[str, Any]:
        return {
            "action_id": new_id("act"),
            "run_id": task.get("run_id"),
            "task_id": task.get("task_id"),
            "instance_id": task.get("instance_id"),
            "device_type": task.get("device_type"),
            "behavior_id": task.get("behavior_id"),
            "payload": deepcopy(task.get("payload", {})),
            "status": "running",
            "sim_time_s": sim_time_s,
            "started_by_signal": task.get("trigger_signal"),
            "source_signal": task.get("source_signal"),
            "route_id": task.get("route_id"),
            "edge_id": task.get("edge_id"),
        }


class RobotArmRuntimeHandler(DefaultDeviceHandler):
    def resolve_behavior(self, spec_doc: dict[str, Any], signal_port: str) -> str | None:
        if signal_port in {"pause_pick", "resume_pick"}:
            return signal_port
        return super().resolve_behavior(spec_doc, signal_port)


class RuntimeHandlerRegistry:
    """Controlled handler registry for signal -> behavior and task -> action dispatch."""

    def __init__(self) -> None:
        self.default_handler = DefaultDeviceHandler()
        self.handlers: dict[str, DefaultDeviceHandler] = {
            "robot_arm": RobotArmRuntimeHandler(),
        }

    def resolve_behavior(self, device_type: str | None, spec_doc: dict[str, Any], signal_port: str) -> str | None:
        return self.handlers.get(device_type or "", self.default_handler).resolve_behavior(spec_doc, signal_port)

    def build_active_action(self, task: dict[str, Any], *, sim_time_s: float | None = None) -> dict[str, Any]:
        return self.handlers.get(task.get("device_type") or "", self.default_handler).build_active_action(task, sim_time_s=sim_time_s)
