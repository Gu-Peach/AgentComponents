from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.ids import new_id


class ActionExecutor:
    """Minimal stateful action executor for SceneBehaviorGraph runtime rules."""

    def __init__(self, graph: dict[str, Any], snapshot: dict[str, Any]) -> None:
        self.graph = graph
        self.snapshot = snapshot

    def start_behavior(
        self,
        *,
        instance_id: str,
        behavior_id: str,
        payload: dict[str, Any] | None = None,
        sim_time_s: float | None = None,
        source_rule_id: str | None = None,
    ) -> dict[str, Any]:
        payload = deepcopy(payload or {})
        resources = self._resources_for_behavior(instance_id, behavior_id)
        locked_by = self._first_locked_resource(resources)
        if locked_by:
            task = self._queue_waiting_action(instance_id, behavior_id, payload, locked_by, source_rule_id)
            return {"status": "waiting_resource", "task": task, "action": None, "frontend_event": None}

        action_id = new_id("act")
        action = {
            "action_id": action_id,
            "instance_id": instance_id,
            "device_type": self._device_type(instance_id),
            "behavior_id": behavior_id,
            "payload": payload,
            "resources": resources,
            "status": "running",
            "sim_time_s": sim_time_s,
            "source_rule_id": source_rule_id,
        }
        for resource_id in resources:
            self.snapshot.setdefault("resource_locks", {})[resource_id] = {"locked_by": action_id, "instance_id": instance_id, "behavior_id": behavior_id}

        self.snapshot.setdefault("active_actions", {})[action_id] = action
        self.snapshot.setdefault("device_states", {})[instance_id] = self._running_state(instance_id, behavior_id)
        self.snapshot.setdefault("device_fsm_states", {})[instance_id] = self._running_state(instance_id, behavior_id)
        self._apply_start_side_effects(instance_id, behavior_id, payload)
        frontend_event = self._append_frontend_event(instance_id, behavior_id, payload, action_id, sim_time_s)
        self._append_event_queue(
            {
                "type": "device_action_started",
                "action_id": action_id,
                "instance_id": instance_id,
                "behavior_id": behavior_id,
                "payload": deepcopy(payload),
                "status": "running",
                "sim_time_s": sim_time_s,
            }
        )
        return {"status": "running", "task": None, "action": action, "frontend_event": frontend_event}

    def complete_action(self, action_id: str, *, sim_time_s: float | None = None) -> dict[str, Any]:
        action = self.snapshot.setdefault("active_actions", {}).pop(action_id, None)
        if not action:
            return {"completed_action": None, "emitted_events": [], "released_resources": [], "reason": "action_not_found"}

        action["status"] = "done"
        action["completed_at_sim_time_s"] = sim_time_s
        released = self._release_resources(action_id)
        instance_id = action["instance_id"]
        self.snapshot.setdefault("device_states", {})[instance_id] = "idle"
        self.snapshot.setdefault("device_fsm_states", {})[instance_id] = "idle"
        emitted_events = self._completion_events(action)
        self._append_event_queue(
            {
                "type": "device_action_completed",
                "action_id": action_id,
                "instance_id": instance_id,
                "behavior_id": action.get("behavior_id"),
                "payload": deepcopy(action.get("payload", {})),
                "status": "done",
                "sim_time_s": sim_time_s,
            }
        )
        return {"completed_action": action, "emitted_events": emitted_events, "released_resources": released}

    def check_timeouts(self, *, current_sim_time_s: float, timeout_s: float = 30.0, max_retries: int = 1) -> dict[str, Any]:
        timed_out: list[dict[str, Any]] = []
        retry_tasks: list[dict[str, Any]] = []
        for action in list(self.snapshot.setdefault("active_actions", {}).values()):
            started_at = action.get("sim_time_s")
            if started_at is None or current_sim_time_s - started_at <= timeout_s:
                continue
            action["status"] = "timeout"
            retry_key = action["action_id"]
            retries = self.snapshot.setdefault("retry_counts", {}).get(retry_key, 0)
            timed_out.append(action)
            if retries < max_retries:
                self.snapshot["retry_counts"][retry_key] = retries + 1
                retry_task = {
                    "task_id": new_id("task"),
                    "instance_id": action["instance_id"],
                    "device_type": action.get("device_type"),
                    "behavior_id": action["behavior_id"],
                    "payload": deepcopy(action.get("payload", {})),
                    "status": "pending_retry",
                    "retry_of_action_id": action["action_id"],
                }
                self.snapshot.setdefault("device_tasks", []).append(retry_task)
                retry_tasks.append(retry_task)
        return {"timed_out_actions": timed_out, "retry_tasks": retry_tasks}

    def detect_deadlock(self) -> dict[str, Any] | None:
        active = [action for action in self.snapshot.get("active_actions", {}).values() if action.get("status") == "running"]
        pending = [task for task in self.snapshot.get("device_tasks", []) if task.get("status") in {"pending", "pending_retry"}]
        waiting = [task for queues in self.snapshot.get("wait_queues", {}).values() for task in queues]
        if active or pending or waiting or self._completion_met():
            return None
        event = {"event_id": "observation.deadlock_detected", "payload": {"reason": "no_enabled_behavior_and_completion_not_met"}}
        self._append_event_queue({"type": "observation", **event})
        return event

    def apply_runtime_event_state(self, event_id: str, payload: dict[str, Any]) -> None:
        if event_id == "conveyor.blocked":
            conveyor_id = payload.get("conveyor_id")
            if conveyor_id:
                self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {})["blocked"] = True
        elif event_id == "conveyor.capacity_available":
            conveyor_id = payload.get("conveyor_id")
            if conveyor_id:
                self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {})["blocked"] = False
        elif event_id == "robot.pause_pick":
            robot_id = payload.get("robot_id")
            if robot_id:
                self.snapshot.setdefault("device_states", {})[robot_id] = "waiting_downstream"
                self.snapshot.setdefault("device_fsm_states", {})[robot_id] = "waiting_downstream"
        elif event_id == "robot.resume_pick":
            robot_id = payload.get("robot_id")
            if robot_id and robot_id not in self._active_instances():
                self.snapshot.setdefault("device_states", {})[robot_id] = "idle"
                self.snapshot.setdefault("device_fsm_states", {})[robot_id] = "idle"

    def _apply_start_side_effects(self, instance_id: str, behavior_id: str, payload: dict[str, Any]) -> None:
        if behavior_id == "accept_material":
            conveyor_id = instance_id
            material_id = payload.get("material_id")
            point_id = payload.get("point_id") or self._first_available_stop_point(conveyor_id)
            if point_id and material_id:
                self.snapshot.setdefault("conveyor_occupancy", {}).setdefault(conveyor_id, {})[point_id] = material_id
            load = self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {"current_load": 0, "max_capacity": 1, "resume_threshold": 1, "blocked": False})
            load["current_load"] = int(load.get("current_load", 0)) + 1
        elif behavior_id == "release_material":
            conveyor_id = instance_id
            load = self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {"current_load": 0, "max_capacity": 1, "resume_threshold": 1, "blocked": False})
            load["current_load"] = max(0, int(load.get("current_load", 0)) - 1)

    def _completion_events(self, action: dict[str, Any]) -> list[dict[str, Any]]:
        instance_id = action["instance_id"]
        behavior_id = action["behavior_id"]
        payload = action.get("payload", {})
        if behavior_id == "pick_and_place":
            material_id = payload.get("material_id")
            target_conveyor = payload.get("target_conveyor_id") or payload.get("target_conveyor")
            if material_id:
                self.snapshot.setdefault("workpiece_pool", {}).setdefault("remaining_parts", {}).setdefault("completed", []).append(material_id)
            events = [{"event_id": "robot.pick_done", "payload": {"robot_id": instance_id, "material_id": material_id, "target_conveyor": target_conveyor}}]
            if target_conveyor:
                events.append({"event_id": "output_conveyor.material_arrived", "payload": {"conveyor_id": target_conveyor, "material_id": material_id}})
            return events
        if behavior_id == "transport_to_exit" and instance_id.startswith("main_conveyor_"):
            next_conveyor_id = "main_conveyor_2" if instance_id == "main_conveyor_1" else ""
            return [{"event_id": f"{instance_id}.pallet_ready", "payload": {"carrier_id": "pallet_1", "location": f"{instance_id}.exit", "next_conveyor_id": next_conveyor_id}}]
        if behavior_id == "release_material":
            conveyor_id = instance_id
            events = [{"event_id": "conveyor.stop_point_released", "payload": {"conveyor_id": conveyor_id, **payload}}]
            load = self.snapshot.get("conveyor_loads", {}).get(conveyor_id, {})
            if load.get("blocked") is True and int(load.get("current_load", 0)) <= int(load.get("resume_threshold", 0)):
                events.append({"event_id": "conveyor.capacity_available", "payload": {"conveyor_id": conveyor_id, "current_load": load.get("current_load"), "resume_threshold": load.get("resume_threshold")}})
            return events
        return []

    def _resources_for_behavior(self, instance_id: str, behavior_id: str) -> list[str]:
        if behavior_id == "pick_and_place":
            return [f"{instance_id}.robot_arm", f"{instance_id}.gripper"]
        if behavior_id in {"transport_to_exit", "advance_to_next_stop_point", "accept_material", "release_material"}:
            return [f"{instance_id}.belt_surface"]
        return []

    def _first_locked_resource(self, resources: list[str]) -> str | None:
        locks = self.snapshot.setdefault("resource_locks", {})
        for resource_id in resources:
            if locks.get(resource_id, {}).get("locked_by"):
                return resource_id
        return None

    def _queue_waiting_action(self, instance_id: str, behavior_id: str, payload: dict[str, Any], resource_id: str, source_rule_id: str | None) -> dict[str, Any]:
        task = {
            "task_id": new_id("task"),
            "instance_id": instance_id,
            "device_type": self._device_type(instance_id),
            "behavior_id": behavior_id,
            "payload": payload,
            "status": "waiting_resource",
            "waiting_for_resource": resource_id,
            "source_rule_id": source_rule_id,
        }
        self.snapshot.setdefault("wait_queues", {}).setdefault(f"resource:{resource_id}", []).append(task)
        return task

    def _release_resources(self, action_id: str) -> list[str]:
        released: list[str] = []
        for resource_id, lock in list(self.snapshot.setdefault("resource_locks", {}).items()):
            if lock.get("locked_by") == action_id:
                released.append(resource_id)
                self.snapshot["resource_locks"].pop(resource_id, None)
        return released

    def _append_frontend_event(self, instance_id: str, behavior_id: str, payload: dict[str, Any], action_id: str, sim_time_s: float | None) -> dict[str, Any]:
        sequence = len(self.snapshot.setdefault("frontend_events", [])) + 1
        event = {
            "event_id": new_id("fevt"),
            "type": "device_behavior_triggered",
            "sequence": sequence,
            "instance_id": instance_id,
            "behavior_id": behavior_id,
            "payload": deepcopy(payload),
            "action_id": action_id,
            "sim_time_s": sim_time_s,
        }
        self.snapshot["frontend_events"].append(event)
        return event

    def _append_event_queue(self, event: dict[str, Any]) -> None:
        self.snapshot.setdefault("event_queue", []).append({"event_id": event.get("event_id") or new_id("evt"), **event})

    def _running_state(self, instance_id: str, behavior_id: str) -> str:
        return "moving" if "conveyor" in instance_id or behavior_id in {"transport_to_exit", "advance_to_next_stop_point", "accept_material", "release_material"} else "busy"

    def _device_type(self, instance_id: str) -> str | None:
        for module in self.graph.get("modules", []):
            if instance_id in module.get("devices", []):
                return "conveyor" if "conveyor" in instance_id else "robot_arm" if "robot" in instance_id else None
        return "conveyor" if "conveyor" in instance_id else "robot_arm" if "robot" in instance_id else None

    def _first_available_stop_point(self, conveyor_id: str) -> str | None:
        for point_id, material_id in self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).items():
            if material_id is None:
                return point_id
        return None

    def _active_instances(self) -> set[str]:
        return {action.get("instance_id") for action in self.snapshot.get("active_actions", {}).values()}

    def _completion_met(self) -> bool:
        remaining = self.snapshot.get("workpiece_pool", {}).get("remaining_parts", {})
        initial_items = set(remaining.get("initial_items", []))
        completed = set(remaining.get("completed", []))
        if initial_items and not initial_items <= completed:
            return False
        loads = self.snapshot.get("conveyor_loads", {})
        if any(int(load.get("current_load", 0)) != 0 for load in loads.values()):
            return False
        return True
