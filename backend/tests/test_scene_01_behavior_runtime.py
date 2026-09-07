from __future__ import annotations

import json
from pathlib import Path

from app.services.behavior_graph_runtime import BehaviorGraphRuntime
from app.services.scene_behavior_graph_validator import validate_scene_behavior_graph_for_runtime


SCENE_01 = Path("tests/scene_01/scene_behavior_graph.golden.json")


def load_scene_01() -> dict:
    return json.loads(SCENE_01.read_text(encoding="utf-8-sig"))


def test_scene_01_json_is_runtime_compatible_before_execution() -> None:
    validation = validate_scene_behavior_graph_for_runtime(load_scene_01())

    assert validation["valid"] is True
    assert validation["summary"] == {"events": 15, "topics": 2, "routes": 10, "behavior_rules": 13}
    assert validation["issues"] == [
        {
            "severity": "warning",
            "code": "MISSING_SOURCE_TOPOLOGY_GRAPH",
            "message": "SceneBehaviorGraph is missing source_topology_graph.",
            "path": "source_topology_graph",
        }
    ]


def test_scene_01_pallet_ready_fans_out_to_two_robot_behaviors() -> None:
    runtime = BehaviorGraphRuntime(load_scene_01())

    result = runtime.emit_event("main_conveyor_2.pallet_ready", {"carrier_id": "pallet_1", "location": "main_conveyor_2.exit"}, sim_time_s=10.0)

    robot_actions = [action for action in result["actions"] if action["behavior_id"] == "pick_and_place"]
    assert [(action["instance_id"], action["payload"]["material_id"], action["payload"]["target_conveyor_id"]) for action in robot_actions] == [
        ("robot_1", "part_001", "upper_out_conveyor_1"),
        ("robot_2", "part_002", "lower_out_conveyor_1"),
    ]
    assert [(event["sequence"], event["instance_id"], event["behavior_id"]) for event in result["frontend_events"]] == [
        (1, "robot_1", "pick_and_place"),
        (2, "robot_2", "pick_and_place"),
    ]
    assert result["snapshot"]["material_claims"]["part_001"] == {"claimed_by": "robot_1", "source_slot": "pallet_1.slot_01"}
    assert result["snapshot"]["material_claims"]["part_002"] == {"claimed_by": "robot_2", "source_slot": "pallet_1.slot_02"}
    assert result["snapshot"]["device_states"]["robot_1"] == "busy"
    assert result["snapshot"]["device_states"]["robot_2"] == "busy"


def test_scene_01_backpressure_pauses_and_resumes_affected_robots() -> None:
    runtime = BehaviorGraphRuntime(load_scene_01())
    runtime.snapshot["conveyor_loads"]["upper_out_conveyor_1"]["current_load"] = 3
    runtime.snapshot["conveyor_loads"]["upper_out_conveyor_1"]["max_capacity"] = 3

    blocked = runtime.emit_event("output_conveyor.material_arrived", {"conveyor_id": "upper_out_conveyor_1", "material_id": "part_099"}, sim_time_s=20.0)

    assert blocked["snapshot"]["conveyor_loads"]["upper_out_conveyor_1"]["blocked"] is True
    assert blocked["snapshot"]["device_states"]["robot_1"] == "waiting_downstream"
    assert blocked["snapshot"]["device_states"]["robot_2"] == "waiting_downstream"
    assert {event["payload"]["robot_id"] for event in blocked["emitted_events"] if event["event_id"] == "robot.pause_pick"} == {"robot_1", "robot_2"}

    runtime.snapshot["conveyor_loads"]["upper_out_conveyor_1"]["current_load"] = 2
    resumed = runtime.emit_event("conveyor.stop_point_released", {"conveyor_id": "upper_out_conveyor_1", "material_id": "part_099"}, sim_time_s=30.0)

    assert resumed["snapshot"]["conveyor_loads"]["upper_out_conveyor_1"]["blocked"] is False
    assert resumed["snapshot"]["device_states"]["robot_1"] == "idle"
    assert resumed["snapshot"]["device_states"]["robot_2"] == "idle"
    assert {event["payload"]["robot_id"] for event in resumed["emitted_events"] if event["event_id"] == "robot.resume_pick"} == {"robot_1", "robot_2"}


def test_scene_01_action_completion_emits_downstream_material_arrival() -> None:
    runtime = BehaviorGraphRuntime(load_scene_01())
    started = runtime.emit_event("main_conveyor_2.pallet_ready", {"carrier_id": "pallet_1", "location": "main_conveyor_2.exit"}, sim_time_s=10.0)
    robot_1_action = next(action for action in started["actions"] if action["instance_id"] == "robot_1")

    completed = runtime.complete_action(robot_1_action["action_id"], sim_time_s=15.0)

    assert any(event["event_id"] == "robot.pick_done" for event in completed["emitted_events"])
    assert any(event["event_id"] == "output_conveyor.material_arrived" for event in completed["emitted_events"])
    assert completed["snapshot"]["device_states"]["robot_1"] == "idle"
    assert completed["snapshot"]["conveyor_loads"]["upper_out_conveyor_1"]["current_load"] == 1
    assert any(event["instance_id"] == "upper_out_conveyor_1" and event["behavior_id"] == "accept_material" for event in completed["frontend_events"])


def test_scene_01_resource_timeout_and_deadlock_helpers() -> None:
    runtime = BehaviorGraphRuntime(load_scene_01())
    first = runtime.executor.start_behavior(instance_id="robot_1", behavior_id="pick_and_place", payload={"material_id": "part_001"}, sim_time_s=0.0)
    second = runtime.executor.start_behavior(instance_id="robot_1", behavior_id="pick_and_place", payload={"material_id": "part_002"}, sim_time_s=1.0)

    assert first["status"] == "running"
    assert second["status"] == "waiting_resource"
    assert runtime.snapshot["wait_queues"]["resource:robot_1.robot_arm"][0]["behavior_id"] == "pick_and_place"

    timeout = runtime.check_timeouts(current_sim_time_s=31.0, timeout_s=30.0, max_retries=1)
    assert timeout["timed_out_actions"][0]["status"] == "timeout"
    assert timeout["retry_tasks"][0]["status"] == "pending_retry"

    empty_runtime = BehaviorGraphRuntime(load_scene_01())
    deadlock = empty_runtime.detect_deadlock()
    assert deadlock == {"event_id": "observation.deadlock_detected", "payload": {"reason": "no_enabled_behavior_and_completion_not_met"}}
