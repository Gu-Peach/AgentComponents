from __future__ import annotations

from typing import Any


def validate_scene_behavior_graph_for_runtime(graph: dict[str, Any]) -> dict[str, Any]:
    """Validate the SceneBehaviorGraph shape required by the backend runtime."""

    issues: list[dict[str, Any]] = []
    if graph.get("schema_type") != "SceneBehaviorGraph":
        issues.append({"severity": "error", "code": "INVALID_SCHEMA_TYPE", "message": "schema_type must be SceneBehaviorGraph.", "path": "schema_type"})

    required_sections = [
        "goal",
        "source_topology_graph",
        "modules",
        "event_bus",
        "state_model",
        "behavior_rules",
        "state_transition_rules",
        "policies",
        "completion_conditions",
        "failure_observations",
    ]
    for section in required_sections:
        if section in graph:
            continue
        severity = "warning" if section == "source_topology_graph" else "error"
        issues.append(
            {
                "severity": severity,
                "code": f"MISSING_{section.upper()}",
                "message": f"SceneBehaviorGraph is missing {section}.",
                "path": section,
            }
        )

    event_bus = graph.get("event_bus", {})
    event_ids = {event.get("event_id") for event in event_bus.get("events", []) if event.get("event_id")}
    topic_ids = {topic.get("topic_id") for topic in event_bus.get("topics", []) if topic.get("topic_id")}
    rule_ids = {rule.get("rule_id") for rule in graph.get("behavior_rules", []) if rule.get("rule_id")}

    if not event_ids:
        issues.append({"severity": "error", "code": "EVENT_BUS_EMPTY", "message": "event_bus.events must define runtime events.", "path": "event_bus.events"})
    if not rule_ids:
        issues.append({"severity": "error", "code": "BEHAVIOR_RULES_EMPTY", "message": "behavior_rules must define executable rules.", "path": "behavior_rules"})

    subscriptions = event_bus.get("subscriptions", {})
    for route_index, route in enumerate(event_bus.get("routes", [])):
        route_path = f"event_bus.routes[{route_index}]"
        if route.get("from") not in event_ids:
            issues.append({"severity": "warning", "code": "ROUTE_SOURCE_NOT_REGISTERED", "message": f"Route source is not registered: {route.get('from')}", "path": f"{route_path}.from"})
        target = route.get("to", {})
        target_type = target.get("type")
        target_id = target.get("id")
        if target_type == "rule" and target_id not in rule_ids:
            issues.append({"severity": "error", "code": "ROUTE_TARGET_RULE_MISSING", "message": f"Route target rule is missing: {target_id}", "path": f"{route_path}.to.id"})
        if target_type == "topic":
            if target_id not in topic_ids:
                issues.append({"severity": "error", "code": "ROUTE_TARGET_TOPIC_MISSING", "message": f"Route target topic is missing: {target_id}", "path": f"{route_path}.to.id"})
            if target_id not in subscriptions:
                issues.append({"severity": "warning", "code": "TOPIC_HAS_NO_SUBSCRIPTIONS", "message": f"Topic has no subscriptions: {target_id}", "path": f"event_bus.subscriptions.{target_id}"})

    for rule_index, rule in enumerate(graph.get("behavior_rules", [])):
        rule_path = f"behavior_rules[{rule_index}]"
        for field in ["rule_id", "module_id", "trigger", "guard", "action"]:
            if field not in rule:
                issues.append({"severity": "error", "code": f"RULE_MISSING_{field.upper()}", "message": f"Rule is missing {field}.", "path": f"{rule_path}.{field}"})
        trigger = rule.get("trigger", {})
        if trigger.get("type") == "event" and trigger.get("event_id") not in event_ids:
            issues.append({"severity": "warning", "code": "RULE_TRIGGER_NOT_REGISTERED", "message": f"Rule trigger is not registered: {trigger.get('event_id')}", "path": f"{rule_path}.trigger.event_id"})

    state_model = graph.get("state_model", {})
    for field in ["device_states", "signal_values", "resource_locks", "active_actions"]:
        if field not in state_model:
            issues.append({"severity": "error", "code": f"STATE_MODEL_MISSING_{field.upper()}", "message": f"state_model is missing {field}.", "path": f"state_model.{field}"})
    if "conveyor_loads" in state_model:
        for conveyor_id, load in state_model["conveyor_loads"].items():
            for field in ["current_load", "max_capacity", "resume_threshold", "blocked"]:
                if field not in load:
                    issues.append({"severity": "error", "code": "CONVEYOR_LOAD_INCOMPLETE", "message": f"conveyor_loads.{conveyor_id} is missing {field}.", "path": f"state_model.conveyor_loads.{conveyor_id}.{field}"})

    return {
        "valid": not any(issue["severity"] == "error" for issue in issues),
        "issues": issues,
        "summary": {
            "events": len(event_ids),
            "topics": len(topic_ids),
            "routes": len(event_bus.get("routes", [])),
            "behavior_rules": len(rule_ids),
        },
    }
