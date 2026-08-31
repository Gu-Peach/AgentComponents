"""Smoke validation for the local demo runner."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from agent.scene_behavior_agent.graph.runner import invoke_agent
from agent.scene_behavior_agent.schemas.config import default_config


def main() -> None:
    config = default_config()
    scene_path = config.simulation_schema_root / "demo" / "pallet_sorting_line" / "full_chain_schema.json"
    with TemporaryDirectory() as tmp_dir:
        state = invoke_agent(
            {
                "scene_document_ref": str(scene_path),
                "user_goal_raw": "托盘到位后由两台机械臂持续分拣物料。",
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
    print("demo validation passed")


if __name__ == "__main__":
    main()
