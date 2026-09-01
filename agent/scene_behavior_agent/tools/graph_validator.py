"""Deterministic validation for generated SceneBehaviorGraph drafts."""

from __future__ import annotations

from typing import Any

from ..schemas.state import ValidationIssue, ValidationReport

REQUIRED_SECTIONS = [
    "goal",
    "modules",
    "event_bus",
    "state_model",
    "behavior_rules",
    "state_transition_rules",
    "policies",
    "completion_conditions",
    "failure_observations",
]


class GraphValidator:
    def validate(
        self,
        graph: dict[str, Any],
        scene_facts: dict[str, Any],
        device_capabilities: dict[str, Any],
    ) -> ValidationReport:
        issues: list[ValidationIssue] = []
        for section in REQUIRED_SECTIONS:
            if section not in graph:
                issues.append({"severity": "error", "code": "missing_section", "message": f"Missing section: {section}", "path": section})

        event_bus = graph.get("event_bus", {})
        event_ids = {event.get("event_id") for event in event_bus.get("events", []) if event.get("event_id")}
        topic_ids = {topic.get("topic_id") for topic in event_bus.get("topics", []) if topic.get("topic_id")}
        subscriptions = event_bus.get("subscriptions", {})
        rule_ids = {rule.get("rule_id") for rule in graph.get("behavior_rules", []) if rule.get("rule_id")}
        instance_index = scene_facts.get("instance_index", {})
        behavior_index = device_capabilities.get("behavior_index", {})

        self._validate_conveyor_specs(device_capabilities, issues)
        self._validate_conveyor_state_model(graph, scene_facts, issues)
        self._validate_conveyor_policies(graph, scene_facts, issues)
        self._validate_conveyor_behavior_rules(graph, scene_facts, issues)
        self._validate_event_bus(event_bus, event_ids, topic_ids, subscriptions, issues)
        self._validate_rules(graph, event_ids, subscriptions, rule_ids, instance_index, behavior_index, scene_facts, issues)
        self._validate_transitions(graph, event_ids, issues)

        return {"valid": not any(issue["severity"] == "error" for issue in issues), "issues": issues}

    @staticmethod
    def _validate_conveyor_specs(device_capabilities: dict[str, Any], issues: list[ValidationIssue]) -> None:
        specs = device_capabilities.get("specs", {})
        for spec_id, spec in specs.items():
            if spec.get("device_type") != "conveyor":
                continue
            stop_point_model = spec.get("type_specific_contract", {}).get("stop_point_model")
            if not stop_point_model:
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_conveyor_stop_point_model",
                        "message": f"Conveyor DeviceSpec {spec_id} must define type_specific_contract.stop_point_model",
                        "path": f"device_capabilities.specs.{spec_id}.type_specific_contract.stop_point_model",
                    }
                )

    @staticmethod
    def _validate_conveyor_state_model(graph: dict[str, Any], scene_facts: dict[str, Any], issues: list[ValidationIssue]) -> None:
        conveyors = [instance for instance in scene_facts.get("instances", []) if instance.get("device_type") == "conveyor"]
        if not conveyors:
            return
        state_model = graph.get("state_model", {})
        required_sections = ["conveyor_stop_points", "conveyor_occupancy", "conveyor_queues", "conveyor_loads"]
        for section in required_sections:
            if section not in state_model:
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_conveyor_state_model",
                        "message": f"SceneBehaviorGraph.state_model must include {section} when conveyors are present",
                        "path": f"state_model.{section}",
                    }
                )
                continue
            for conveyor in conveyors:
                conveyor_id = conveyor.get("instance_id")
                if conveyor_id and conveyor_id not in state_model.get(section, {}):
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "missing_conveyor_state_entry",
                            "message": f"State model section {section} has no entry for conveyor {conveyor_id}",
                            "path": f"state_model.{section}.{conveyor_id}",
                        }
                    )

    @staticmethod
    def _validate_conveyor_policies(graph: dict[str, Any], scene_facts: dict[str, Any], issues: list[ValidationIssue]) -> None:
        if not any(instance.get("device_type") == "conveyor" for instance in scene_facts.get("instances", [])):
            return
        policies = graph.get("policies", {})
        policy_types = {policy.get("type") for policy in policies.values() if isinstance(policy, dict)}
        for policy_type in ["queue_wait", "capacity_threshold", "nearest_available_stop_point", "downstream_release"]:
            if policy_type not in policy_types:
                issues.append(
                    {
                        "severity": "error",
                        "code": "missing_conveyor_policy",
                        "message": f"Conveyor behavior graph must define a {policy_type} policy",
                        "path": "policies",
                    }
                )

    @staticmethod
    def _validate_conveyor_behavior_rules(graph: dict[str, Any], scene_facts: dict[str, Any], issues: list[ValidationIssue]) -> None:
        if not any(instance.get("device_type") == "conveyor" for instance in scene_facts.get("instances", [])):
            return
        required_rule_ids = {
            "accept_material_to_first_available_stop_point",
            "advance_material_to_next_stop_point",
            "wait_when_next_stop_point_occupied",
            "release_material_when_downstream_available",
            "emit_blocked_when_no_stop_point_available",
            "emit_capacity_available_when_stop_point_released",
        }
        rule_ids = {rule.get("rule_id") for rule in graph.get("behavior_rules", []) if rule.get("rule_id")}
        for rule_id in sorted(required_rule_ids - rule_ids):
            issues.append(
                {
                    "severity": "error",
                    "code": "missing_conveyor_behavior_rule",
                    "message": f"Conveyor behavior graph must define rule {rule_id}",
                    "path": f"behavior_rules.{rule_id}",
                }
            )

    def validate_connections(self, scene_facts: dict[str, Any], device_capabilities: dict[str, Any]) -> ValidationReport:
        issues: list[ValidationIssue] = []
        instance_index = scene_facts.get("instance_index", {})
        signal_ports = device_capabilities.get("signal_port_index", {})
        missing_specs = device_capabilities.get("missing", [])
        for spec_id in missing_specs:
            issues.append({"severity": "error", "code": "missing_device_spec", "message": f"DeviceSpec not found: {spec_id}"})

        for edge in scene_facts.get("signal_edges", []):
            for endpoint_key in ("source", "target"):
                endpoint = edge.get(endpoint_key, "")
                if "." not in endpoint:
                    issues.append({"severity": "error", "code": "invalid_signal_endpoint", "message": f"Invalid signal endpoint: {endpoint}"})
                    continue
                instance_id, port_id = endpoint.split(".", 1)
                instance = instance_index.get(instance_id)
                if not instance:
                    issues.append({"severity": "error", "code": "unknown_instance", "message": f"Unknown instance in signal edge: {instance_id}"})
                    continue
                spec_id = instance.get("spec_id")
                if port_id not in signal_ports.get(spec_id, []):
                    issues.append(
                        {
                            "severity": "warning",
                            "code": "unknown_signal_port",
                            "message": f"Signal port {port_id} not found in spec {spec_id}",
                            "path": edge.get("edge_id", "signal_edges"),
                        }
                    )
        return {"valid": not any(issue["severity"] == "error" for issue in issues), "issues": issues}

    @staticmethod
    def _validate_event_bus(
        event_bus: dict[str, Any],
        event_ids: set[str],
        topic_ids: set[str],
        subscriptions: dict[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        for route in event_bus.get("routes", []):
            route_id = route.get("route_id", "<unknown>")
            source_event = route.get("from")
            if source_event not in event_ids:
                issues.append({"severity": "error", "code": "unknown_route_event", "message": f"Route {route_id} references unknown event {source_event}"})
            target = route.get("to", {})
            target_type = target.get("type")
            target_id = target.get("id")
            if target_type == "topic":
                if target_id not in topic_ids:
                    issues.append({"severity": "error", "code": "unknown_topic", "message": f"Route {route_id} references unknown topic {target_id}"})
                if target_id not in subscriptions:
                    issues.append({"severity": "error", "code": "missing_topic_subscription", "message": f"Topic {target_id} has no subscriptions"})
        for topic_id in topic_ids:
            if topic_id not in subscriptions:
                issues.append({"severity": "warning", "code": "unused_topic", "message": f"Topic {topic_id} has no subscriptions"})

    @staticmethod
    def _validate_rules(
        graph: dict[str, Any],
        event_ids: set[str],
        subscriptions: dict[str, Any],
        rule_ids: set[str],
        instance_index: dict[str, Any],
        behavior_index: dict[str, list[str]],
        scene_facts: dict[str, Any],
        issues: list[ValidationIssue],
    ) -> None:
        subscription_event_ids = {
            item.get("message_event_id")
            for items in subscriptions.values()
            for item in items
            if isinstance(item, dict) and item.get("message_event_id")
        }
        valid_trigger_events = event_ids | subscription_event_ids
        for rule in graph.get("behavior_rules", []):
            rule_id = rule.get("rule_id", "<unknown>")
            trigger_event = rule.get("trigger", {}).get("event_id")
            if trigger_event and trigger_event not in valid_trigger_events:
                issues.append({"severity": "error", "code": "unknown_trigger_event", "message": f"Rule {rule_id} triggers on unknown event {trigger_event}"})
            action = rule.get("action", {})
            instance_id = action.get("instance_id")
            behavior_id = action.get("behavior_id")
            if instance_id and isinstance(instance_id, str) and not instance_id.startswith("trigger.") and not instance_id.startswith("policy."):
                if instance_id not in instance_index:
                    issues.append({"severity": "error", "code": "unknown_action_instance", "message": f"Rule {rule_id} references unknown instance {instance_id}"})
                elif behavior_id:
                    spec_id = instance_index[instance_id].get("spec_id")
                    if behavior_id not in behavior_index.get(spec_id, []):
                        issues.append({"severity": "error", "code": "unknown_behavior", "message": f"Rule {rule_id} references behavior {behavior_id} not in {spec_id}"})
            target = rule.get("action", {}).get("target")
            if target and isinstance(target, str) and target in rule_ids:
                issues.append({"severity": "warning", "code": "ambiguous_action_target", "message": f"Rule {rule_id} action target points to rule id {target}"})

    @staticmethod
    def _validate_transitions(graph: dict[str, Any], event_ids: set[str], issues: list[ValidationIssue]) -> None:
        for transition in graph.get("state_transition_rules", []):
            rule_id = transition.get("rule_id", "<unknown>")
            for effect in transition.get("effects", []):
                if not isinstance(effect, str) or "emit " not in effect:
                    continue
                emitted = effect.split("emit ", 1)[1].strip().split()[0]
                if emitted not in event_ids and not emitted.startswith("observation."):
                    issues.append({"severity": "warning", "code": "unregistered_emitted_event", "message": f"Transition {rule_id} emits unregistered event {emitted}"})
