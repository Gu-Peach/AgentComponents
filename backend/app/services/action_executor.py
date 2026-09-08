from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.ids import new_id


CONVEYOR_BEHAVIORS = {"transport_to_exit", "advance_to_next_stop_point", "accept_material", "release_material"}
CONVEYOR_MOVE_BEHAVIORS = {"transport_to_exit", "advance_to_next_stop_point"}


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
        payload = self.prepare_behavior_payload(instance_id, behavior_id, payload or {})
        if self._must_wait_for_stop_point(instance_id, behavior_id, payload):
            task = self._queue_waiting_conveyor_action(instance_id, behavior_id, payload, source_rule_id)
            return {"status": "waiting_conveyor", "task": task, "action": None, "frontend_event": None}

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
        self.apply_start_side_effects(instance_id, behavior_id, payload)
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
        emitted_events = self.apply_completion_side_effects(action)
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

    def complete_task(self, task: dict[str, Any], *, sim_time_s: float | None = None) -> dict[str, Any]:
        task["completed_at_sim_time_s"] = sim_time_s
        emitted_events = self.apply_completion_side_effects(task) if task.get("status") == "done" else []
        return {"completed_task": task, "emitted_events": emitted_events, "released_resources": []}

    def prepare_behavior_payload(self, instance_id: str, behavior_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        prepared = deepcopy(payload or {})
        if behavior_id not in CONVEYOR_BEHAVIORS:
            return prepared

        material_id = self._material_id(prepared)
        prepared.setdefault("conveyor_id", instance_id)
        if material_id:
            prepared.setdefault("material_id", material_id)

        if behavior_id == "accept_material":
            point_id = self._payload_point(prepared, "point_id", "to_point_id", "to_stop_point_id", "target_stop_point_id") or self._first_available_stop_point(instance_id)
            if point_id:
                prepared.setdefault("point_id", point_id)
                prepared.setdefault("to_point_id", point_id)
                prepared.setdefault("to_stop_point_id", point_id)
                prepared.setdefault("target_stop_point_id", point_id)
            return prepared

        if behavior_id in CONVEYOR_MOVE_BEHAVIORS:
            from_point_id = self._payload_point(prepared, "from_point_id", "from_stop_point_id") or self._current_stop_point_for_material(instance_id, material_id) or self._entry_stop_point(instance_id)
            to_point_id = self._payload_point(prepared, "to_point_id", "to_stop_point_id") or self._next_stop_point(instance_id, from_point_id)
            if behavior_id == "transport_to_exit":
                prepared.setdefault("transport_goal_behavior_id", "transport_to_exit")
            if from_point_id:
                prepared.setdefault("from_point_id", from_point_id)
                prepared.setdefault("from_stop_point_id", from_point_id)
            if to_point_id:
                prepared.setdefault("to_point_id", to_point_id)
                prepared.setdefault("to_stop_point_id", to_point_id)
            return prepared

        if behavior_id == "release_material":
            from_point_id = self._payload_point(prepared, "from_point_id", "from_stop_point_id", "point_id") or self._exit_stop_point(instance_id)
            if from_point_id:
                prepared.setdefault("from_point_id", from_point_id)
                prepared.setdefault("from_stop_point_id", from_point_id)
                prepared.setdefault("point_id", from_point_id)
            material_at_exit = self._material_at_stop_point(instance_id, from_point_id)
            if material_at_exit:
                prepared.setdefault("material_id", material_at_exit)
            return prepared

        return prepared

    def apply_start_side_effects(self, instance_id: str, behavior_id: str, payload: dict[str, Any]) -> None:
        if behavior_id == "accept_material":
            self._occupy_stop_point(instance_id, payload.get("point_id") or payload.get("to_point_id"), self._material_id(payload), increment_load=True)
        elif behavior_id == "transport_to_exit":
            self._occupy_stop_point(instance_id, payload.get("from_point_id"), self._material_id(payload), increment_load=True)

    def apply_completion_side_effects(self, action: dict[str, Any]) -> list[dict[str, Any]]:
        instance_id = action["instance_id"]
        behavior_id = action["behavior_id"]
        payload = action.get("payload", {})

        if behavior_id == "accept_material":
            return self._accept_material_events(instance_id, payload)
        if behavior_id in CONVEYOR_MOVE_BEHAVIORS:
            return self._complete_conveyor_move(instance_id, behavior_id, payload)
        if behavior_id == "release_material":
            return self._complete_conveyor_release(instance_id, payload)
        if behavior_id == "pick_and_place":
            return self._complete_robot_pick(action)
        return []

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
        elif event_id == "conveyor.stop_point_occupied":
            self._occupy_stop_point(payload.get("conveyor_id"), payload.get("point_id"), self._material_id(payload), increment_load=False)
        elif event_id == "conveyor.stop_point_released":
            self._release_stop_point(payload.get("conveyor_id"), payload.get("point_id"), self._material_id(payload), decrement_load=False)
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

    def _complete_robot_pick(self, action: dict[str, Any]) -> list[dict[str, Any]]:
        instance_id = action["instance_id"]
        payload = action.get("payload", {})
        material_id = payload.get("material_id")
        target_conveyor = payload.get("target_conveyor_id") or payload.get("target_conveyor")
        if material_id:
            self.snapshot.setdefault("workpiece_pool", {}).setdefault("remaining_parts", {}).setdefault("completed", []).append(material_id)
        events = [{"event_id": "robot.pick_done", "payload": {"robot_id": instance_id, "material_id": material_id, "target_conveyor": target_conveyor}}]
        if target_conveyor:
            events.append({"event_id": "output_conveyor.material_arrived", "payload": {"conveyor_id": target_conveyor, "material_id": material_id}})
        return events

    def _accept_material_events(self, conveyor_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        material_id = self._material_id(payload)
        point_id = payload.get("point_id") or payload.get("to_point_id")
        if not material_id or not point_id:
            return []
        return [
            {
                "event_id": "conveyor.stop_point_occupied",
                "payload": {
                    "conveyor_id": conveyor_id,
                    "material_id": material_id,
                    "point_id": point_id,
                    "to_point_id": point_id,
                    "arrived_by_behavior": "accept_material",
                },
            }
        ]

    def _complete_conveyor_move(self, conveyor_id: str, behavior_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        material_id = self._material_id(payload)
        from_point_id = payload.get("from_point_id")
        to_point_id = payload.get("to_point_id")
        if not material_id or not from_point_id or not to_point_id:
            if behavior_id == "transport_to_exit" and conveyor_id.startswith("main_conveyor_"):
                next_conveyor_id = "main_conveyor_2" if conveyor_id == "main_conveyor_1" else ""
                return [{"event_id": f"{conveyor_id}.pallet_ready", "payload": {"carrier_id": "pallet_1", "location": f"{conveyor_id}.exit", "next_conveyor_id": next_conveyor_id}}]
            return []

        self._release_stop_point(conveyor_id, from_point_id, material_id, decrement_load=False)
        self._occupy_stop_point(conveyor_id, to_point_id, material_id, increment_load=False)

        events = [
            {
                "event_id": "conveyor.stop_point_released",
                "payload": {
                    "conveyor_id": conveyor_id,
                    "material_id": material_id,
                    "point_id": from_point_id,
                    "from_point_id": from_point_id,
                    "to_point_id": to_point_id,
                    "released_by_behavior": behavior_id,
                },
            },
            {
                "event_id": "conveyor.stop_point_occupied",
                "payload": {
                    "conveyor_id": conveyor_id,
                    "material_id": material_id,
                    "point_id": to_point_id,
                    "from_point_id": from_point_id,
                    "to_point_id": to_point_id,
                    "arrived_by_behavior": behavior_id,
                    "transport_goal_behavior_id": payload.get("transport_goal_behavior_id"),
                    "carrier_id": payload.get("carrier_id"),
                },
            },
        ]
        if self._is_exit_stop_point(conveyor_id, to_point_id) and payload.get("transport_goal_behavior_id") == "transport_to_exit" and conveyor_id.startswith("main_conveyor_"):
            next_conveyor_id = "main_conveyor_2" if conveyor_id == "main_conveyor_1" else ""
            events.append(
                {
                    "event_id": f"{conveyor_id}.pallet_ready",
                    "payload": {
                        "carrier_id": payload.get("carrier_id") or material_id,
                        "material_id": material_id,
                        "location": f"{conveyor_id}.{to_point_id}",
                        "point_id": to_point_id,
                        "next_conveyor_id": next_conveyor_id,
                    },
                }
            )
        return events

    def _complete_conveyor_release(self, conveyor_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        from_point_id = payload.get("from_point_id") or payload.get("point_id") or self._exit_stop_point(conveyor_id)
        material_id = self._material_id(payload) or self._material_at_stop_point(conveyor_id, from_point_id)
        self._release_stop_point(conveyor_id, from_point_id, material_id, decrement_load=True)
        events = [
            {
                "event_id": "conveyor.stop_point_released",
                "payload": {
                    "conveyor_id": conveyor_id,
                    "material_id": material_id,
                    "point_id": from_point_id,
                    "from_point_id": from_point_id,
                    **payload,
                },
            }
        ]
        load = self.snapshot.get("conveyor_loads", {}).get(conveyor_id, {})
        if load.get("blocked") is True and int(load.get("current_load", 0)) <= int(load.get("resume_threshold", 0)):
            events.append({"event_id": "conveyor.capacity_available", "payload": {"conveyor_id": conveyor_id, "current_load": load.get("current_load"), "resume_threshold": load.get("resume_threshold")}})
        return events

    def _must_wait_for_stop_point(self, instance_id: str, behavior_id: str, payload: dict[str, Any]) -> bool:
        if behavior_id == "accept_material":
            return bool(self._material_id(payload)) and not bool(payload.get("point_id") or payload.get("to_point_id"))
        if behavior_id in CONVEYOR_MOVE_BEHAVIORS:
            from_point_id = payload.get("from_point_id")
            to_point_id = payload.get("to_point_id")
            return bool(from_point_id) and not bool(to_point_id) and not self._is_exit_stop_point(instance_id, from_point_id)
        return False

    def _occupy_stop_point(self, conveyor_id: str | None, point_id: str | None, material_id: str | None, *, increment_load: bool) -> None:
        if not conveyor_id or not point_id or not material_id:
            return
        occupancy = self.snapshot.setdefault("conveyor_occupancy", {}).setdefault(conveyor_id, {})
        already_on_conveyor = self._current_stop_point_for_material(conveyor_id, material_id) is not None
        occupancy[point_id] = material_id
        self.snapshot.setdefault("material_locations", {})[material_id] = f"{conveyor_id}.{point_id}"
        if increment_load and not already_on_conveyor:
            load = self._conveyor_load(conveyor_id)
            load["current_load"] = int(load.get("current_load", 0)) + 1
            if int(load.get("current_load", 0)) >= int(load.get("max_capacity", 1)):
                load["blocked"] = True

    def _release_stop_point(self, conveyor_id: str | None, point_id: str | None, material_id: str | None, *, decrement_load: bool) -> None:
        if not conveyor_id or not point_id:
            return
        occupancy = self.snapshot.setdefault("conveyor_occupancy", {}).setdefault(conveyor_id, {})
        if material_id is None or occupancy.get(point_id) in {None, material_id}:
            occupancy[point_id] = None
        if decrement_load:
            load = self._conveyor_load(conveyor_id)
            load["current_load"] = max(0, int(load.get("current_load", 0)) - 1)
            if int(load.get("current_load", 0)) <= int(load.get("resume_threshold", 0)):
                load["blocked"] = False
            if material_id:
                self.snapshot.setdefault("material_locations", {})[material_id] = f"{conveyor_id}.released"

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

    def _queue_waiting_conveyor_action(self, instance_id: str, behavior_id: str, payload: dict[str, Any], source_rule_id: str | None) -> dict[str, Any]:
        material_id = self._material_id(payload)
        point_id = payload.get("from_point_id") or payload.get("point_id") or self._current_stop_point_for_material(instance_id, material_id)
        wait_queue = self.snapshot.setdefault("wait_queues", {}).setdefault(f"conveyor:{instance_id}", [])
        for existing in wait_queue:
            existing_payload = existing.get("payload", {}) if isinstance(existing.get("payload"), dict) else {}
            existing_material_id = self._material_id(existing_payload) or existing.get("material_id")
            existing_point_id = existing.get("waiting_at_point_id") or existing_payload.get("from_point_id") or existing.get("point_id")
            if existing_material_id == material_id and existing_point_id == point_id and existing.get("behavior_id") == behavior_id:
                return existing
        task = {
            "task_id": new_id("task"),
            "instance_id": instance_id,
            "device_type": self._device_type(instance_id),
            "behavior_id": behavior_id,
            "payload": payload,
            "status": "waiting_conveyor",
            "waiting_for_conveyor": instance_id,
            "waiting_at_point_id": point_id,
            "source_rule_id": source_rule_id,
        }
        wait_queue.append(task)
        waiting_materials = self.snapshot.setdefault("conveyor_queues", {}).setdefault(instance_id, {"queue_id": f"{instance_id}.stop_point_queue", "waiting_materials": []}).setdefault("waiting_materials", [])
        if not any(item.get("material_id") == material_id and item.get("point_id") == point_id for item in waiting_materials):
            waiting_materials.append({"material_id": material_id, "point_id": point_id, "task_id": task["task_id"]})
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

    def _resources_for_behavior(self, instance_id: str, behavior_id: str) -> list[str]:
        if behavior_id == "pick_and_place":
            return [f"{instance_id}.robot_arm", f"{instance_id}.gripper"]
        if behavior_id in CONVEYOR_BEHAVIORS:
            return [f"{instance_id}.belt_surface"]
        return []

    def _first_locked_resource(self, resources: list[str]) -> str | None:
        locks = self.snapshot.setdefault("resource_locks", {})
        for resource_id in resources:
            if locks.get(resource_id, {}).get("locked_by"):
                return resource_id
        return None

    def _running_state(self, instance_id: str, behavior_id: str) -> str:
        return "moving" if "conveyor" in instance_id or behavior_id in CONVEYOR_BEHAVIORS else "busy"

    def _device_type(self, instance_id: str) -> str | None:
        for module in self.graph.get("modules", []):
            if instance_id in module.get("devices", []):
                return "conveyor" if "conveyor" in instance_id else "robot_arm" if "robot" in instance_id else None
        return "conveyor" if "conveyor" in instance_id else "robot_arm" if "robot" in instance_id else None

    def _ordered_stop_point_ids(self, conveyor_id: str | None) -> list[str]:
        if not conveyor_id:
            return []
        points = self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])
        ordered = [point.get("point_id") for point in sorted(points, key=lambda item: item.get("index", 0)) if point.get("point_id")]
        return ordered or list(self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).keys())

    def _entry_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        for point in self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", []):
            if point.get("role") == "entry":
                return point.get("point_id")
        ordered = self._ordered_stop_point_ids(conveyor_id)
        return ordered[0] if ordered else None

    def _exit_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        for point in self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", []):
            if point.get("role") == "exit":
                return point.get("point_id")
        ordered = self._ordered_stop_point_ids(conveyor_id)
        return ordered[-1] if ordered else None

    def _next_stop_point(self, conveyor_id: str | None, point_id: str | None) -> str | None:
        ordered = self._ordered_stop_point_ids(conveyor_id)
        if not point_id or point_id not in ordered:
            return None
        index = ordered.index(point_id)
        return ordered[index + 1] if index + 1 < len(ordered) else None

    def _first_available_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        occupancy = self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {})
        for point_id in self._ordered_stop_point_ids(conveyor_id):
            if occupancy.get(point_id) is None:
                return point_id
        return None

    def _current_stop_point_for_material(self, conveyor_id: str | None, material_id: str | None) -> str | None:
        if not conveyor_id or not material_id:
            return None
        for point_id, current_material in self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).items():
            if current_material == material_id:
                return point_id
        return None

    def _material_at_stop_point(self, conveyor_id: str | None, point_id: str | None) -> str | None:
        if not conveyor_id or not point_id:
            return None
        value = self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(point_id)
        return value if isinstance(value, str) else None

    def _is_exit_stop_point(self, conveyor_id: str | None, point_id: str | None) -> bool:
        return bool(point_id) and point_id == self._exit_stop_point(conveyor_id)

    def _conveyor_load(self, conveyor_id: str) -> dict[str, Any]:
        return self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {"current_load": 0, "max_capacity": 1, "resume_threshold": 1, "blocked": False})

    @staticmethod
    def _material_id(payload: dict[str, Any] | None) -> str | None:
        if not payload:
            return None
        for key in ["material_id", "carrier_id", "subject_id", "workpiece_id", "object_id"]:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    @staticmethod
    def _payload_point(payload: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
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
