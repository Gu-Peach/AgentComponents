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

            routed_rule_ids: set[str] = set()
            routes = self.routes_by_source.get(event["event_id"], [])
            for route in routes:
                target = route.get("to", {})
                target_type = target.get("type")
                if target_type == "rule":
                    rule_id = target.get("id")
                    if rule_id:
                        routed_rule_ids.add(rule_id)
                    queue.extend(self._run_rule(rule_id, event, result, sim_time_s=sim_time_s))
                elif target_type == "topic":
                    queue.extend(self._publish_topic(target.get("id"), event, result, sim_time_s=sim_time_s))
            for rule_id in self._rule_ids_for_event(event["event_id"]):
                if rule_id not in routed_rule_ids:
                    queue.extend(self._run_rule(rule_id, event, result, sim_time_s=sim_time_s))
            if event["event_id"] in {"conveyor.stop_point_released", "conveyor.capacity_available"}:
                self._resume_waiting_conveyor_materials(event, result, sim_time_s=sim_time_s)

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
        if self._is_exit_stop_point_queue_wait(rule, event):
            result["skipped_rules"].append({"rule_id": rule_id, "event_id": event["event_id"], "reason": "exit_stop_point_has_no_next_stop_point"})
            return []
        if not self._guard_matches(rule.get("guard", {}), event) and not self._policy_wait_condition_matches(rule, event):
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
            payload = self._payload_with_policy_outputs(payload, policy_outputs)
            payload = self._inherit_runtime_payload(payload, event)
            started = self.executor.start_behavior(instance_id=instance_id, behavior_id=behavior_id, payload=payload, sim_time_s=sim_time_s, source_rule_id=rule.get("rule_id"))
            if started.get("action"):
                result["actions"].append(started["action"])
            if started.get("frontend_event"):
                result["frontend_events"].append(started["frontend_event"])
            if started.get("task"):
                result["waiting_tasks"].append(started["task"])
            if started.get("status") == "running":
                return self._policy_side_effect_events(policy_outputs, sim_time_s=sim_time_s)
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
        if policy_id == "downstream_release":
            return self._policy_downstream_release(inputs)
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

    def _policy_downstream_release(self, inputs: dict[str, Any]) -> dict[str, Any]:
        conveyor_id = inputs.get("conveyor_id")
        point_id = inputs.get("point_id")
        if conveyor_id and point_id:
            return {"from_point_id": point_id, "to_point_id": self._next_stop_point(conveyor_id, point_id)}

        from_conveyor_id = inputs.get("from_conveyor_id")
        to_conveyor_id = inputs.get("to_conveyor_id")
        if from_conveyor_id and to_conveyor_id:
            release_point_id = self._exit_stop_point(from_conveyor_id)
            return {
                "release_conveyor_id": from_conveyor_id,
                "release_point_id": release_point_id,
                "material_id": inputs.get("material_id") or self._material_at_stop_point(from_conveyor_id, release_point_id),
            }

        if conveyor_id:
            exit_point_id = self._exit_stop_point(conveyor_id)
            return {
                "from_point_id": exit_point_id,
                "point_id": exit_point_id,
                "material_id": inputs.get("material_id") or self._material_at_stop_point(conveyor_id, exit_point_id),
            }

        return {}

    def _policy_wait_condition_matches(self, rule: dict[str, Any], event: dict[str, Any]) -> bool:
        if rule.get("policy", {}).get("policy_id") != "conveyor_queue_wait":
            return False
        if event.get("event_id") != "conveyor.stop_point_occupied":
            return False
        payload = event.get("payload", {})
        conveyor_id = payload.get("conveyor_id")
        point_id = payload.get("point_id")
        if not conveyor_id or not point_id or self._is_exit_stop_point(conveyor_id, point_id):
            return False
        next_point_id = self._next_stop_point(conveyor_id, point_id)
        return next_point_id is not None and self._material_at_stop_point(conveyor_id, next_point_id) is not None

    def _is_exit_stop_point_queue_wait(self, rule: dict[str, Any], event: dict[str, Any]) -> bool:
        if rule.get("policy", {}).get("policy_id") != "conveyor_queue_wait":
            return False
        if event.get("event_id") != "conveyor.stop_point_occupied":
            return False
        payload = event.get("payload", {})
        return self._is_exit_stop_point(payload.get("conveyor_id"), payload.get("point_id"))

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
        if expression.startswith("trigger."):
            trigger_path = expression.removeprefix("trigger.")
            direct_value = self._nested_get(event, trigger_path)
            return direct_value if direct_value is not None else self._nested_get(event.get("payload", {}), trigger_path)
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
            if next_point is None:
                return True
            return self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(next_point) is not None
        if expression.startswith("exit_stop_point(") and expression.endswith(").occupied"):
            conveyor_id = self._resolve_expr_value(expression.removeprefix("exit_stop_point(").removesuffix(").occupied"), event)
            point_id = self._exit_stop_point(conveyor_id)
            return self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(point_id) is not None
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
        if template.startswith("trigger."):
            trigger_path = template.removeprefix("trigger.")
            direct_value = self._nested_get(event, trigger_path)
            return direct_value if direct_value is not None else self._nested_get(event.get("payload", {}), trigger_path)
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

    @staticmethod
    def _payload_with_policy_outputs(payload: Any, policy_outputs: dict[str, Any]) -> dict[str, Any]:
        merged = deepcopy(payload) if isinstance(payload, dict) else {}
        for key in [
            "material_id",
            "carrier_id",
            "point_id",
            "from_point_id",
            "to_point_id",
            "from_stop_point_id",
            "to_stop_point_id",
            "target_conveyor_id",
        ]:
            value = policy_outputs.get(key)
            if value is not None:
                merged.setdefault(key, value)
        return merged

    @staticmethod
    def _inherit_runtime_payload(payload: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        inherited = deepcopy(payload)
        source_payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
        for key in [
            "carrier_id",
            "material_id",
            "subject_id",
            "workpiece_id",
            "transport_goal_behavior_id",
            "from_conveyor_id",
            "to_conveyor_id",
        ]:
            value = source_payload.get(key)
            if value is not None:
                inherited.setdefault(key, value)
        return inherited

    def _policy_side_effect_events(self, policy_outputs: dict[str, Any], *, sim_time_s: float | None) -> list[dict[str, Any]]:
        conveyor_id = policy_outputs.get("release_conveyor_id")
        point_id = policy_outputs.get("release_point_id")
        if not conveyor_id or not point_id:
            return []

        material_id = policy_outputs.get("material_id") or self._material_at_stop_point(conveyor_id, point_id)
        self._release_stop_point(conveyor_id, point_id, material_id, decrement_load=True)
        return [
            {
                "event_id": "conveyor.stop_point_released",
                "payload": {
                    "conveyor_id": conveyor_id,
                    "point_id": point_id,
                    "from_point_id": point_id,
                    "material_id": material_id,
                    "released_by_policy": "downstream_release",
                },
                "sim_time_s": sim_time_s,
                "source": "policy:downstream_release",
            }
        ]

    def _resume_waiting_conveyor_materials(self, event: dict[str, Any], result: dict[str, Any], *, sim_time_s: float | None) -> None:
        conveyor_id = event.get("payload", {}).get("conveyor_id")
        if not conveyor_id or self._conveyor_blocked(conveyor_id) or self._conveyor_has_active_action(conveyor_id):
            return

        queue_key = f"conveyor:{conveyor_id}"
        waiting_items = list(self.snapshot.setdefault("wait_queues", {}).get(queue_key, []))
        if not waiting_items:
            return

        for item in self._sort_waiting_items_towards_exit(conveyor_id, waiting_items):
            item_payload = deepcopy(item.get("payload", item)) if isinstance(item, dict) else {}
            material_id = self._material_id(item_payload) or item.get("material_id")
            point_id = item.get("waiting_at_point_id") or item_payload.get("from_point_id") or item.get("point_id") or self._current_stop_point_for_material(conveyor_id, material_id)
            next_point_id = self._next_stop_point(conveyor_id, point_id)
            if not material_id or not point_id or not next_point_id:
                continue
            if self._material_at_stop_point(conveyor_id, next_point_id) is not None:
                continue

            item_payload.setdefault("material_id", material_id)
            item_payload.setdefault("from_point_id", point_id)
            item_payload.setdefault("from_stop_point_id", point_id)
            item_payload.setdefault("to_point_id", next_point_id)
            item_payload.setdefault("to_stop_point_id", next_point_id)
            started = self.executor.start_behavior(
                instance_id=conveyor_id,
                behavior_id=item.get("behavior_id") or "advance_to_next_stop_point",
                payload=item_payload,
                sim_time_s=sim_time_s,
                source_rule_id=item.get("source_rule_id") or "runtime_resume_waiting_conveyor_materials",
            )
            if started.get("action"):
                self._remove_waiting_item(conveyor_id, material_id, point_id, task_id=item.get("task_id"))
                result["actions"].append(started["action"])
            if started.get("frontend_event"):
                result["frontend_events"].append(started["frontend_event"])
            if started.get("task"):
                result["waiting_tasks"].append(started["task"])
            if started.get("status") == "running":
                break

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

    def _ordered_stop_point_ids(self, conveyor_id: str | None) -> list[str]:
        if not conveyor_id:
            return []
        points = self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])
        ordered = [point.get("point_id") for point in sorted(points, key=lambda item: item.get("index", 0)) if point.get("point_id")]
        return ordered or list(self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).keys())

    def _entry_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        points = self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])
        for point in points:
            if point.get("role") == "entry":
                return point.get("point_id")
        ordered = self._ordered_stop_point_ids(conveyor_id)
        return ordered[0] if ordered else None

    def _exit_stop_point(self, conveyor_id: str | None) -> str | None:
        if not conveyor_id:
            return None
        points = self.snapshot.get("conveyor_stop_points", {}).get(conveyor_id, {}).get("points", [])
        for point in points:
            if point.get("role") == "exit":
                return point.get("point_id")
        ordered = self._ordered_stop_point_ids(conveyor_id)
        return ordered[-1] if ordered else None

    def _next_stop_point(self, conveyor_id: str | None, point_id: str | None) -> str | None:
        if not conveyor_id or not point_id:
            return None
        ordered = self._ordered_stop_point_ids(conveyor_id)
        if point_id not in ordered:
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
        material_id = self.snapshot.get("conveyor_occupancy", {}).get(conveyor_id, {}).get(point_id)
        return material_id if isinstance(material_id, str) else None

    def _is_exit_stop_point(self, conveyor_id: str | None, point_id: str | None) -> bool:
        return bool(point_id) and point_id == self._exit_stop_point(conveyor_id)

    def _release_stop_point(self, conveyor_id: str | None, point_id: str | None, material_id: str | None, *, decrement_load: bool) -> None:
        if not conveyor_id or not point_id:
            return
        occupancy = self.snapshot.setdefault("conveyor_occupancy", {}).setdefault(conveyor_id, {})
        if material_id is None or occupancy.get(point_id) in {None, material_id}:
            occupancy[point_id] = None
        if decrement_load:
            load = self.snapshot.setdefault("conveyor_loads", {}).setdefault(conveyor_id, {"current_load": 0, "max_capacity": 1, "resume_threshold": 1, "blocked": False})
            load["current_load"] = max(0, int(load.get("current_load", 0)) - 1)
            if int(load.get("current_load", 0)) <= int(load.get("resume_threshold", 0)):
                load["blocked"] = False
            if material_id:
                self.snapshot.setdefault("material_locations", {})[material_id] = f"{conveyor_id}.released"

    def _conveyor_blocked(self, conveyor_id: str) -> bool:
        return bool(self.snapshot.get("conveyor_loads", {}).get(conveyor_id, {}).get("blocked", False))

    def _conveyor_has_active_action(self, conveyor_id: str) -> bool:
        return any(action.get("instance_id") == conveyor_id and action.get("status") == "running" for action in self.snapshot.get("active_actions", {}).values())

    def _sort_waiting_items_towards_exit(self, conveyor_id: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        order = {point_id: index for index, point_id in enumerate(self._ordered_stop_point_ids(conveyor_id))}
        return sorted(items, key=lambda item: order.get(item.get("waiting_at_point_id") or item.get("point_id") or item.get("payload", {}).get("from_point_id"), -1), reverse=True)

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
        waiting_materials = self.snapshot.setdefault("conveyor_queues", {}).setdefault(conveyor_id, {"queue_id": f"{conveyor_id}.stop_point_queue", "waiting_materials": []}).setdefault("waiting_materials", [])
        wait_queue = self.snapshot.setdefault("wait_queues", {}).setdefault(f"conveyor:{conveyor_id}", [])
        if not any(entry.get("material_id") == material_id and entry.get("point_id") == point_id for entry in waiting_materials):
            waiting_materials.append(deepcopy(item))
        if not any(self._waiting_item_matches(entry, material_id, point_id, None) for entry in wait_queue):
            wait_queue.append(item)

    def _remove_waiting_item(self, conveyor_id: str, material_id: str | None, point_id: str | None, *, task_id: str | None = None) -> None:
        queue_key = f"conveyor:{conveyor_id}"
        self.snapshot.setdefault("wait_queues", {})[queue_key] = [
            item
            for item in self.snapshot.setdefault("wait_queues", {}).get(queue_key, [])
            if not self._waiting_item_matches(item, material_id, point_id, task_id)
        ]
        conveyor_queue = self.snapshot.setdefault("conveyor_queues", {}).setdefault(conveyor_id, {"queue_id": f"{conveyor_id}.stop_point_queue", "waiting_materials": []})
        conveyor_queue["waiting_materials"] = [
            item
            for item in conveyor_queue.get("waiting_materials", [])
            if not self._waiting_item_matches(item, material_id, point_id, task_id)
        ]

    def _waiting_item_matches(self, item: dict[str, Any], material_id: str | None, point_id: str | None, task_id: str | None) -> bool:
        if task_id and item.get("task_id") == task_id:
            return True
        payload = item.get("payload", {}) if isinstance(item.get("payload"), dict) else item
        item_material_id = self._material_id(payload) or item.get("material_id")
        item_point_id = item.get("waiting_at_point_id") or item.get("point_id") or payload.get("from_point_id")
        return item_material_id == material_id and (point_id is None or item_point_id == point_id)

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
    def _empty_result() -> dict[str, Any]:
        return {"emitted_events": [], "fired_rules": [], "skipped_rules": [], "actions": [], "frontend_events": [], "waiting_tasks": [], "completed_actions": []}

    @staticmethod
    def _merge_result(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key in ["emitted_events", "fired_rules", "skipped_rules", "actions", "frontend_events", "waiting_tasks", "completed_actions"]:
            target.setdefault(key, []).extend(source.get(key, []))


class _Missing:
    pass


_MISSING = _Missing()
