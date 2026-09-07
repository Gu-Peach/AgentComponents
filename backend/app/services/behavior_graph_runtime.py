from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.services.action_executor import ActionExecutor
from app.services.ids import new_id


class BehaviorGraphRuntime:
    """Interpret a SceneBehaviorGraph with minimal deterministic runtime semantics."""

    def __init__(self, behavior_graph: dict[str, Any], snapshot: dict[str, Any] | None = None) -> None:
        self.graph = behavior_graph
        self.snapshot = deepcopy(snapshot or behavior_graph.get("state_model", {}))
        self.snapshot.setdefault("event_queue", [])
        self.snapshot.setdefault("frontend_events", [])
        self.snapshot.setdefault("device_tasks", [])
        self.snapshot.setdefault("device_fsm_states", deepcopy(self.snapshot.get("device_states", {})))
        self.snapshot.setdefault("resource_locks", {})
        self.snapshot.setdefault("active_actions", {})
        self.snapshot.setdefault("wait_queues", {})
        self.routes_by_source = self._routes_by_source()
        self.rules_by_id = {rule.get("rule_id"): rule for rule in self.graph.get("behavior_rules", []) if rule.get("rule_id")}
        self.executor = ActionExecutor(self.graph, self.snapshot)

    def emit_event(self, event_id: str, payload: dict[str, Any] | None = None, *, sim_time_s: float | None = None) -> dict[str, Any]:
        queue = [{"event_id": event_id, "payload": deepcopy(payload or {}), "sim_time_s": sim_time_s, "source": "external"}]
        result = self._empty_result()
        steps = 0

        while queue:
            steps += 1
            if steps > 200:
                result["skipped_rules"].append({"reason": "max_event_steps_exceeded", "event_id": queue[0].get("event_id")})
                break
            event = queue.pop(0)
            self._record_runtime_event(event)
            self.executor.apply_runtime_event_state(event["event_id"], event.get("payload", {}))
            result["emitted_events"].append(event)

            routes = self.routes_by_source.get(event["event_id"], [])
            for route in routes:
                target = route.get("to", {})
                target_type = target.get("type")
                if target_type == "rule":
                    queue.extend(self._run_rule(target.get("id"), event, result, sim_time_s=sim_time_s))
                elif target_type == "topic":
                    queue.extend(self._publish_topic(target.get("id"), event, result, sim_time_s=sim_time_s))
            if not routes:
                for rule_id in self._rule_ids_for_event(event["event_id"]):
                    queue.extend(self._run_rule(rule_id, event, result, sim_time_s=sim_time_s))

        return {**result, "snapshot": self.snapshot}

    def complete_action(self, action_id: str, *, sim_time_s: float | None = None) -> dict[str, Any]:
        completed = self.executor.complete_action(action_id, sim_time_s=sim_time_s)
        result = self._empty_result()
        result["completed_actions"].append(completed)
        for event in completed.get("emitted_events", []):
            chained = self.emit_event(event["event_id"], event.get("payload", {}), sim_time_s=sim_time_s)
            self._merge_result(result, chained)
        return {**result, "snapshot": self.snapshot}

    def check_timeouts(self, *, current_sim_time_s: float, timeout_s: float = 30.0, max_retries: int = 1) -> dict[str, Any]:
        return self.executor.check_timeouts(current_sim_time_s=current_sim_time_s, timeout_s=timeout_s, max_retries=max_retries)

    def detect_deadlock(self) -> dict[str, Any] | None:
        return self.executor.detect_deadlock()

    def _publish_topic(self, topic_id: str | None, event: dict[str, Any], result: dict[str, Any], *, sim_time_s: float | None) -> list[dict[str, Any]]:
        if not topic_id:
            return []
        queued_events: list[dict[str, Any]] = []
        subscriptions = self.graph.get("event_bus", {}).get("subscriptions", {}).get(topic_id, [])
        for subscription in subscriptions:
            if not self._filter_matches(subscription.get("filter"), event):
                result["skipped_rules"].append({"rule_id": subscription.get("subscriber_id"), "event_id": event["event_id"], "reason": "subscription_filter_not_matched"})
                continue
            message = {
                "event_id": subscription.get("message_event_id") or event["event_id"],
                "payload": self._resolve_template(subscription.get("payload_template", event.get("payload", {})), event, {}),
                "sim_time_s": sim_time_s,
                "source": f"topic:{topic_id}",
            }
            self._record_runtime_event(message)
            result["emitted_events"].append(message)
            if subscription.get("subscriber_type") == "rule":
                queued_events.extend(self._run_rule(subscription.get("subscriber_id"), message, result, sim_time_s=sim_time_s))
        return queued_events

    def _run_rule(self, rule_id: str | None, event: dict[str, Any], result: dict[str, Any], *, sim_time_s: float | None) -> list[dict[str, Any]]:
        rule = self.rules_by_id.get(rule_id or "")
        if not rule:
            result["skipped_rules"].append({"rule_id": rule_id, "event_id": event["event_id"], "reason": "rule_not_found"})
            return []
        trigger = rule.get("trigger", {})
        if trigger.get("type") == "event" and trigger.get("event_id") != event["event_id"]:
            result["skipped_rules"].append({"rule_id": rule_id, "event_id": event["event_id"], "reason": "trigger_not_matched"})
            return []
        if not self._guard_matches(rule.get("guard", {}), event):
            result["skipped_rules"].append({"rule_id": rule_id, "event_id": event["event_id"], "reason": "guard_not_matched"})
            return []

        policy_outputs = self._apply_policy(rule.get("policy"), event)
        result["fired_rules"].append({"rule_id": rule_id, "event_id": event["event_id"], "policy_outputs": policy_outputs})
        return self._execute_action(rule, event, policy_outputs, result, sim_time_s=sim_time_s)

    def _execute_action(self, rule: dict[str, Any], event: dict[str, Any], policy_outputs: dict[str, Any], result: dict[str, Any], *, sim_time_s: float | None) -> list[dict[str, Any]]:
        action = rule.get("action", {})
        action_type = action.get("type")
        if action_type in {"start_behavior", "start_or_continue_behavior"}:
            instance_id = self._resolve_template(action.get("instance_id"), event, policy_outputs)
            behavior_id = action.get("behavior_id")
            if not instance_id or not behavior_id:
                result["skipped_rules"].append({"rule_id": rule.get("rule_id"), "reason": "missing_behavior_target"})
                return []
            if action_type == "start_or_continue_behavior" and self._has_active_behavior(instance_id, behavior_id):
                result["skipped_rules"].append({"rule_id": rule.get("rule_id"), "reason": "behavior_already_running", "instance_id": instance_id, "behavior_id": behavior_id})
                return []
            payload = self._resolve_template(action.get("payload", {}), event, policy_outputs)
            started = self.executor.start_behavior(instance_id=instance_id, behavior_id=behavior_id, payload=payload, sim_time_s=sim_time_s, source_rule_id=rule.get("rule_id"))
            if started.get("action"):
                result["actions"].append(started["action"])
            if started.get("frontend_event"):
                result["frontend_events"].append(started["frontend_event"])
            if started.get("task"):
                result["waiting_tasks"].append(started["task"])
            return []

        if action_type == "emit_event":
            event_id = action.get("event_id")
            payload = self._resolve_template(action.get("payload", {}), event, policy_outputs)
            target = self._resolve_template(action.get("target"), event, policy_outputs) if "target" in action else None
            return self._events_for_emit_action(event_id, payload, target, sim_time_s)

        if action_type == "update_state":
            self._apply_update_state(action.get("payload", {}), event, policy_outputs)
            return []

        result["skipped_rules"].append({"rule_id": rule.get("rule_id"), "reason": "unsupported_action", "action_type": action_type})
        return []

    def _apply_policy(self, policy: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
        if not policy:
            return {}
        policy_id = policy.get("policy_id")
        inputs = self._resolve_template(policy.get("inputs", {}), event, {})
        if policy_id == "claim_workpiece":
            return self._policy_claim_workpiece(inputs)
        if policy_id == "target_conveyor_selection":
            return {"target_conveyor_id": self._policy_target_conveyor(inputs)}
        if policy_id == "backpressure":
            return self._policy_backpressure(inputs, event)
        if policy_id == "conveyor_stop_point_selection":
            return {"point_id": self._first_available_stop_point(inputs.get("conveyor_id"))}
        if policy_id == "conveyor_queue_wait":
            self._append_wait_queue(inputs.get("conveyor_id"), inputs.get("material_id"), inputs.get("point_id"))
        return {}

    def _policy_claim_workpiece(self, inputs: dict[str, Any]) -> dict[str, Any]:
        robot_id = inputs.get("robot_id")
        pool = self.snapshot.setdefault("workpiece_pool", {}).setdefault("remaining_parts", {})
        claimed = pool.setdefault("claimed", {})
        completed = set(pool.setdefault("completed", []))
        for material_id in pool.get("initial_items", []):
            if material_id in claimed or material_id in completed:
                continue
            source_slot = self._source_slot_for_material(material_id)
            claimed[material_id] = robot_id
            self.snapshot.setdefault("material_claims", {})[material_id] = {"claimed_by": robot_id, "source_slot": source_slot}
            return {"material_id": material_id, "source_slot": source_slot}
        return {"material_id": None, "source_slot": None}

    @staticmethod
    def _source_slot_for_material(material_id: str) -> str | None:
        if "_" not in material_id:
            return None
        try:
            return f"pallet_1.slot_{int(material_id.rsplit('_', 1)[-1]):02d}"
        except ValueError:
            return None

    def _policy_target_conveyor(self, inputs: dict[str, Any]) -> str | None:
        robot_id = inputs.get("robot_id")
        preferred = {"robot_1": "upper_out_conveyor_1", "robot_2": "lower_out_conveyor_1"}.get(robot_id)
        loads = self.snapshot.get("conveyor_loads", {})
        if preferred in loads and not loads[preferred].get("blocked", False):
            return preferred
        candidates = [(cid, load) for cid, load in loads.items() if "out_conveyor" in cid and not load.get("blocked", False)]
        if not candidates:
            candidates = [(cid, load) for cid, load in loads.items() if "out_conveyor" in cid]
        if not candidates:
            return None
        return sorted(candidates, key=lambda item: (int(item[1].get("current_load", 0)), item[0]))[0][0]

    def _policy_backpressure(self, inputs: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        conveyor_id = inputs.get("conveyor_id") or event.get("payload", {}).get("conveyor_id")
        if conveyor_id:
            load = self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {"current_load": 0, "max_capacity": 1, "resume_threshold": 1, "blocked": False})
            if event["event_id"] == "conveyor.blocked":
                load["blocked"] = True
            elif event["event_id"] == "conveyor.capacity_available":
                load["blocked"] = False
        target_robots: list[str] = []
        for binding in self.graph.get("event_bus", {}).get("backpressure_bindings", []):
            if binding.get("conveyor_id") == conveyor_id:
                target_robots.extend(binding.get("affected_robots", []))
        return {"target_robots": target_robots}

    def _guard_matches(self, guard: dict[str, Any], event: dict[str, Any]) -> bool:
        all_exprs = guard.get("all", [])
        any_exprs = guard.get("any", [])
        none_exprs = guard.get("none", [])
        return all(self._eval_expression(expr, event) for expr in all_exprs) and (not any_exprs or any(self._eval_expression(expr, event) for expr in any_exprs)) and not any(self._eval_expression(expr, event) for expr in none_exprs)

    def _filter_matches(self, expression: str | None, event: dict[str, Any]) -> bool:
        return True if not expression else self._eval_expression(expression, event)

    def _eval_expression(self, expression: str, event: dict[str, Any]) -> bool:
        expression = expression.strip()
        if " in [" in expression:
            left, raw_values = expression.split(" in [", 1)
            values = [self._resolve_expr_value(item.strip()) for item in raw_values.rstrip("]").split(",")]
            return self._resolve_expr_value(left.strip(), event) in values
        for operator in ["<=", ">=", "==", "!=", "<", ">"]:
            if operator not in expression:
                continue
            left, right = [part.strip() for part in expression.split(operator, 1)]
            left_value = self._resolve_expr_value(left, event)
            right_value = self._resolve_expr_value(right, event)
            if operator == "<=":
                return left_value <= right_value
            if operator == ">=":
                return left_value >= right_value
            if operator == "==":
                return left_value == right_value
            if operator == "!=":
                return left_value != right_value
            if operator == "<":
                return left_value < right_value
            if operator == ">":
                return left_value > right_value
        return bool(self._resolve_expr_value(expression, event))

    def _resolve_expr_value(self, expression: str, event: dict[str, Any] | None = None) -> Any:
        event = event or {"event_id": None, "payload": {}}
        if expression in {"true", "false", "null"}:
            return {"true": True, "false": False, "null": None}[expression]
        if expression.replace(".", "", 1).isdigit():
            return float(expression) if "." in expression else int(expression)
        if expression in {"idle", "moving", "busy", "waiting_downstream"}:
            return expression
        if expression.startswith("event.event_id"):
            return event.get("event_id")
        if expression.startswith("trigger.payload."):
            return self._nested_get(event.get("payload", {}), expression.removeprefix("trigger.payload."))
        if expression.startswith("event.payload."):
            return self._nested_get(event.get("payload", {}), expression.removeprefix("event.payload."))
        if expression == "workpiece_pool.remaining_parts.empty":
            return self._remaining_workpieces_empty()
        if expression.startswith("entry_stop_point(") and expression.endswith(").occupied"):
            conveyor_id = self._resolve_expr_value(expression.removeprefix("entry_stop_point(").removesuffix(").occupied"), event)
            point_id = self._entry_stop_point(conveyor_id)
            return self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(point_id) is not None
        if expression.startswith("next_stop_point(") and expression.endswith(").occupied"):
            args = self._split_args(expression.removeprefix("next_stop_point(").removesuffix(").occupied"))
            conveyor_id = self._resolve_expr_value(args[0], event)
            point_id = self._resolve_expr_value(args[1], event)
            next_point = self._next_stop_point(conveyor_id, point_id)
            return self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(next_point) is not None
        if expression.startswith("downstream_available(") and expression.endswith(")"):
            conveyor_id = self._resolve_expr_value(expression.removeprefix("downstream_available(").removesuffix(")"), event)
            return self._downstream_available(conveyor_id)
        if expression.startswith("no_available_stop_point(") and expression.endswith(")"):
            conveyor_id = self._resolve_expr_value(expression.removeprefix("no_available_stop_point(").removesuffix(")"), event)
            return self._first_available_stop_point(conveyor_id) is None
        if expression.startswith("target_conveyors.blocked_for_robot(") and expression.endswith(")"):
            robot_id = self._resolve_expr_value(expression.removeprefix("target_conveyors.blocked_for_robot(").removesuffix(")"), event)
            return self._target_blocked_for_robot(robot_id)
        if expression.startswith("resource(") and expression.endswith(").locked_by"):
            resource_arg = expression.removeprefix("resource(").removesuffix(").locked_by")
            resource_id = self._resource_id(resource_arg, event)
            return self.snapshot.get("resource_locks", {}).get(resource_id, {}).get("locked_by")
        bracket_value = self._resolve_bracket_path(expression, event)
        if bracket_value is not _MISSING:
            return bracket_value
        dot_value = self._resolve_dot_path(expression)
        if dot_value is not _MISSING:
            return dot_value
        return expression.strip('"\'')

    def _resolve_template(self, template: Any, event: dict[str, Any], policy_outputs: dict[str, Any]) -> Any:
        if isinstance(template, dict):
            return {key: self._resolve_template(value, event, policy_outputs) for key, value in template.items()}
        if isinstance(template, list):
            return [self._resolve_template(value, event, policy_outputs) for value in template]
        if not isinstance(template, str):
            return template
        if template == "source_event.payload":
            return deepcopy(event.get("payload", {}))
        if template.startswith("trigger.payload."):
            return self._nested_get(event.get("payload", {}), template.removeprefix("trigger.payload."))
        if template.startswith("event.payload."):
            return self._nested_get(event.get("payload", {}), template.removeprefix("event.payload."))
        if template.startswith("policy."):
            return policy_outputs.get(template.removeprefix("policy."))
        return template

    def _events_for_emit_action(self, event_id: str | None, payload: dict[str, Any], target: Any, sim_time_s: float | None) -> list[dict[str, Any]]:
        if not event_id:
            return []
        targets = target if isinstance(target, list) else [target] if target else [None]
        events: list[dict[str, Any]] = []
        for item in targets:
            event_payload = deepcopy(payload)
            if item and event_id.startswith("robot."):
                event_payload.setdefault("robot_id", item)
            events.append({"event_id": event_id, "payload": event_payload, "sim_time_s": sim_time_s, "source": "rule_action"})
        return events

    def _apply_update_state(self, payload: dict[str, Any], event: dict[str, Any], policy_outputs: dict[str, Any]) -> None:
        append_path = payload.get("append")
        if not append_path:
            return
        material_id = self._resolve_template(payload.get("material_id"), event, policy_outputs)
        conveyor_id = self._resolve_template("trigger.payload.conveyor_id", event, policy_outputs)
        self._append_wait_queue(conveyor_id, material_id, self._resolve_template("trigger.payload.point_id", event, policy_outputs))

    def _record_runtime_event(self, event: dict[str, Any]) -> None:
        self.snapshot.setdefault("signal_values", {})[event["event_id"]] = deepcopy(event.get("payload", {}))
        self.snapshot.setdefault("event_queue", []).append(
            {
                "event_id": new_id("evt"),
                "type": "behavior_graph_event",
                "signal_id": event["event_id"],
                "payload": deepcopy(event.get("payload", {})),
                "status": "delivered",
                "sim_time_s": event.get("sim_time_s"),
                "source": event.get("source"),
            }
        )

    def _routes_by_source(self) -> dict[str, list[dict[str, Any]]]:
        index: dict[str, list[dict[str, Any]]] = {}
        for route in self.graph.get("event_bus", {}).get("routes", []):
            index.setdefault(route.get("from"), []).append(route)
        return index

    def _rule_ids_for_event(self, event_id: str) -> list[str]:
        return [
            rule["rule_id"]
            for rule in self.graph.get("behavior_rules", [])
            if rule.get("rule_id") and rule.get("trigger", {}).get("type") == "event" and rule.get("trigger", {}).get("event_id") == event_id
        ]

    def _has_active_behavior(self, instance_id: str, behavior_id: str) -> bool:
        return any(action.get("instance_id") == instance_id and action.get("behavior_id") == behavior_id and action.get("status") == "running" for action in self.snapshot.get("active_actions", {}).values())

    def _remaining_workpieces_empty(self) -> bool:
        pool = self.snapshot.get("workpiece_pool", {}).get("remaining_parts", {})
        initial_items = set(pool.get("initial_items", []))
        claimed = set(pool.get("claimed", {}).keys())
        completed = set(pool.get("completed", []))
        return not bool(initial_items - claimed - completed)

    def _resolve_bracket_path(self, expression: str, event: dict[str, Any]) -> Any:
        if "[" not in expression or "]" not in expression:
            return _MISSING
        root, rest = expression.split("[", 1)
        key_expr, tail = rest.split("]", 1)
        root_obj = self.snapshot.get(root)
        if root_obj is None:
            return _MISSING
        key = self._resolve_expr_value(key_expr, event)
        value = root_obj.get(key) if isinstance(root_obj, dict) else _MISSING
        if value is _MISSING:
            return _MISSING
        if tail.startswith("."):
            return self._nested_get(value, tail[1:])
        return value

    def _resolve_dot_path(self, expression: str) -> Any:
        if "." not in expression:
            return _MISSING
        root, path = expression.split(".", 1)
        if root not in self.snapshot:
            return _MISSING
        return self._nested_get(self.snapshot[root], path)

    @staticmethod
    def _nested_get(value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @staticmethod
    def _split_args(raw: str) -> list[str]:
        return [item.strip() for item in raw.split(",")]

    def _entry_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        points = self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])
        for point in points:
            if point.get("role") == "entry":
                return point.get("point_id")
        return next(iter(self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {})), None)

    def _next_stop_point(self, conveyor_id: str | None, point_id: str | None) -> str | None:
        if not conveyor_id or not point_id:
            return None
        ordered = [point.get("point_id") for point in self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])]
        if not ordered:
            ordered = list(self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).keys())
        if point_id not in ordered:
            return None
        index = ordered.index(point_id)
        return ordered[index + 1] if index + 1 < len(ordered) else None

    def _first_available_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        for point_id, material_id in self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).items():
            if material_id is None:
                return point_id
        return None

    def _downstream_available(self, conveyor_id: str | None) -> bool:
        if not conveyor_id:
            return False
        if conveyor_id == "main_conveyor_1":
            return not self.snapshot.get("conveyor_loads", {}).get("main_conveyor_2", {}).get("blocked", False)
        load = self.snapshot.get("conveyor_loads", {}).get(conveyor_id, {})
        return not load.get("blocked", False) and int(load.get("current_load", 0)) < int(load.get("max_capacity", 1))

    def _target_blocked_for_robot(self, robot_id: str | None) -> bool:
        if not robot_id:
            return False
        for binding in self.graph.get("event_bus", {}).get("backpressure_bindings", []):
            if robot_id in binding.get("affected_robots", []):
                conveyor_id = binding.get("conveyor_id")
                if self.snapshot.get("conveyor_loads", {}).get(conveyor_id, {}).get("blocked", False):
                    return True
        return False

    def _resource_id(self, expression: str, event: dict[str, Any]) -> str:
        if expression == "trigger.payload.robot_id.gripper":
            return f"{event.get('payload', {}).get('robot_id')}.gripper"
        return expression

    def _append_wait_queue(self, conveyor_id: str | None, material_id: str | None, point_id: str | None) -> None:
        if not conveyor_id or not material_id:
            return
        item = {"material_id": material_id, "point_id": point_id}
        self.snapshot.setdefault("conveyor_queues", {}).setdefault(conveyor_id, {"queue_id": f"{conveyor_id}.stop_point_queue", "waiting_materials": []}).setdefault("waiting_materials", []).append(item)
        self.snapshot.setdefault("wait_queues", {}).setdefault(f"conveyor:{conveyor_id}", []).append(item)

    @staticmethod
    def _empty_result() -> dict[str, Any]:
        return {"emitted_events": [], "fired_rules": [], "skipped_rules": [], "actions": [], "frontend_events": [], "waiting_tasks": [], "completed_actions": []}

    @staticmethod
    def _merge_result(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key in ["emitted_events", "fired_rules", "skipped_rules", "actions", "frontend_events", "waiting_tasks", "completed_actions"]:
            target.setdefault(key, []).extend(source.get(key, []))


class _Missing:
    pass


_MISSING = _Missing()
