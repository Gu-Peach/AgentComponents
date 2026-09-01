"""Smoke validation for the local demo runner."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from agent.scene_behavior_agent.graph.runner import invoke_agent
from agent.scene_behavior_agent.schemas.config import default_config


def main() -> None:
    config = default_config()
    scene_path = config.simulation_schema_root / "2.SceneDocument" / "example.json"
    with TemporaryDirectory() as tmp_dir:
        state = invoke_agent(
            {
                "scene_document_ref": str(scene_path),
                "user_goal_raw": "托盘经两段主传送带到位后，由两台机械臂持续分拣物料；传送带运输必须经过停留点并处理出料传送带 backpressure。",
                "output_path": f"{tmp_dir}/scene_behavior_graph.test.json",
            },
            config=config,
        )
    assert state.get("final_scene_behavior_graph"), state
    graph = state["final_scene_behavior_graph"]
    for key in [
        "goal",
        "modules",
        "event_bus",
        "state_model",
        "behavior_rules",
        "state_transition_rules",
        "policies",
        "completion_conditions",
        "failure_observations",
    ]:
        assert key in graph, key
    assert state.get("validation_report", {}).get("valid"), state.get("validation_report")
    assert any(route.get("to", {}).get("type") == "topic" for route in graph["event_bus"]["routes"])
    event_ids = {event.get("event_id") for event in graph["event_bus"]["events"]}
    route_ids = {route.get("route_id") for route in graph["event_bus"]["routes"]}
    rule_ids = {rule.get("rule_id") for rule in graph["behavior_rules"]}
    policy_types = {policy.get("type") for policy in graph["policies"].values() if isinstance(policy, dict)}
    for key in ["conveyor_stop_points", "conveyor_occupancy", "conveyor_queues", "conveyor_loads"]:
        assert key in graph["state_model"], key
    for event_id in ["conveyor.stop_point_occupied", "conveyor.stop_point_released", "conveyor.blocked", "conveyor.capacity_available"]:
        assert event_id in event_ids, event_id
    assert "route_main_conveyor_1_ready_to_main_conveyor_2_transport_rule" in route_ids
    assert "transfer_pallet_main_conveyor_1_to_main_conveyor_2" in rule_ids
    for policy_type in ["queue_wait", "capacity_threshold", "nearest_available_stop_point", "downstream_release"]:
        assert policy_type in policy_types, policy_type
    assert "output_conveyor.blocked" not in event_ids
    assert "output_conveyor.capacity_available" not in event_ids
    print("demo validation passed")


if __name__ == "__main__":
    main()
