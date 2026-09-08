from __future__ import annotations

import json
from pathlib import Path

from conftest import make_client


SCENE1_DOCUMENT = Path("../frontend/public/test/scene1/scene_document.json")
SCENE1_ROOT = Path("../frontend/public/test/scene1")


def upload_scene1_device_specs(client) -> None:
    bundle = json.loads((SCENE1_ROOT / "device_specs" / "index.json").read_text(encoding="utf-8-sig"))
    for item in bundle["device_specs"]:
        spec = json.loads(Path("..", item["path"]).read_text(encoding="utf-8-sig"))
        response = client.post("/api/device-specs", json={"spec_id": spec.get("device_spec_id") or spec.get("schema_id"), "document": spec})
        assert response.status_code == 200


def create_scene1_runtime(client) -> str:
    upload_scene1_device_specs(client)
    project = client.post("/api/projects", json={"name": "Scene1 local runtime"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    scene = client.get(f"/api/projects/{project_id}/scene").json()
    scene_doc = json.loads(SCENE1_DOCUMENT.read_text(encoding="utf-8-sig"))

    replaced = client.put(
        f"/api/projects/{project_id}/scene",
        json={"base_revision": scene["revision"], "document": scene_doc},
    )
    assert replaced.status_code == 200

    topology = client.post(f"/api/projects/{project_id}/topology/rebuild")
    assert topology.status_code == 200

    run = client.post(f"/api/projects/{project_id}/simulation-runs", json={"base_scene_revision": replaced.json()["new_revision"]})
    assert run.status_code == 200
    return run.json()["run_id"]


def next_frontend_event(client, run_id: str, handled_task_ids: set[str]) -> dict:
    frontend_events = client.get(f"/api/simulation-runs/{run_id}/frontend-events")
    assert frontend_events.status_code == 200
    for event in frontend_events.json()["events"]:
        task_id = event.get("task_id")
        if task_id and task_id not in handled_task_ids:
            return event
    raise AssertionError("No uncompleted frontend event found")


def complete_frontend_event(client, run_id: str, event: dict, completed_task_ids: set[str], sim_time_s: float) -> dict:
    task_id = event["task_id"]
    completed_task_ids.add(task_id)
    response = client.post(
        f"/api/simulation-runs/{run_id}/actions/{task_id}/complete",
        json={"sim_time_s": sim_time_s, "payload": {"completed_by": "frontend_test"}},
    )
    assert response.status_code == 200
    return response.json()


def test_project_scene_edges_compile_topology_and_runtime() -> None:
    client = make_client()
    assert client.get("/health").json()["agent_enabled"] is True

    imported = client.post("/api/device-specs/import-defaults")
    assert imported.status_code == 200
    imported_specs = imported.json()
    assert {item["spec_id"] for item in imported_specs} >= {"conveyor_1", "robot_arm_1"}

    project = client.post("/api/projects", json={"name": "Pallet sorting line"})
    assert project.status_code == 200
    project_id = project.json()["id"]

    scene = client.get(f"/api/projects/{project_id}/scene").json()
    assert scene["revision"] == 0

    add_conveyor = client.post(
        f"/api/projects/{project_id}/scene/instances",
        json={"base_revision": 0, "spec_id": "conveyor_1", "instance_id": "conveyor_1"},
    )
    assert add_conveyor.status_code == 200
    assert add_conveyor.json()["new_revision"] == 1

    conflict = client.post(
        f"/api/projects/{project_id}/scene/instances",
        json={"base_revision": 0, "spec_id": "robot_arm_1", "instance_id": "robot_conflict"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"] == "SCENE_REVISION_CONFLICT"

    add_robot = client.post(
        f"/api/projects/{project_id}/scene/instances",
        json={"base_revision": 1, "spec_id": "robot_arm_1", "instance_id": "robot_1"},
    )
    assert add_robot.status_code == 200

    edge = client.post(
        f"/api/projects/{project_id}/scene/process-edges",
        json={"base_revision": 2, "edge_id": "proc_conveyor_to_robot", "source": "conveyor_1.flow_output", "target": "robot_1.flow_input", "edge_type": "material_flow"},
    )
    assert edge.status_code == 200
    assert edge.json()["new_revision"] == 3

    bad_signal = client.post(
        f"/api/projects/{project_id}/scene/signal-edges",
        json={"base_revision": 3, "source": "robot_1.start_pick", "target": "conveyor_1.part_ready"},
    )
    assert bad_signal.status_code == 422
    assert bad_signal.json()["error"] == "EDGE_VALIDATION_FAILED"

    compiled = client.post(f"/api/projects/{project_id}/interfaces/compile", json={"base_revision": 3, "mode": "dry_run"})
    assert compiled.status_code == 200
    body = compiled.json()
    assert body["compiled_physical_edges"][0]["source"] == "conveyor_1.exit"
    assert any(item["target"] == "robot_1.start_pick" for item in body["compiled_signal_edges"])

    applied = client.post(f"/api/projects/{project_id}/interfaces/compile", json={"base_revision": 3, "mode": "apply"})
    assert applied.status_code == 200
    assert applied.json()["new_revision"] == 4

    topology = client.post(f"/api/projects/{project_id}/topology/rebuild")
    assert topology.status_code == 200
    topo_doc = topology.json()["document"]
    assert topo_doc["process_graph"]["edges"][0]["source"] == "conveyor_1.flow_output"

    reachability = client.get(
        f"/api/projects/{project_id}/topology/reachability",
        params={"source": "conveyor_1.flow_output", "target": "robot_1.flow_input", "graph": "process_graph"},
    )
    assert reachability.status_code == 200
    assert reachability.json()["reachable"] is True

    asset = client.post("/api/assets", json={"bucket": "models", "path": "conveyor/conveyor.glb", "mime_type": "model/gltf-binary", "metadata": {"spec_id": "conveyor_1"}})
    assert asset.status_code == 200
    assert asset.json()["provider"] == "supabase"

    run = client.post(f"/api/projects/{project_id}/simulation-runs", json={})
    assert run.status_code == 200
    run_id = run.json()["run_id"]

    signal = client.post(f"/api/simulation-runs/{run_id}/signals/conveyor_1.part_ready/emit", json={"value": True, "payload": {"material_id": "part_001"}, "sim_time_s": 1.5})
    assert signal.status_code == 200
    assert signal.json()["signal_id"] == "conveyor_1.part_ready"

    frontend_events = client.get(f"/api/simulation-runs/{run_id}/frontend-events")
    assert frontend_events.status_code == 200
    assert frontend_events.json()["events"][0]["type"] == "device_behavior_triggered"
    assert frontend_events.json()["events"][0]["instance_id"] == "robot_1"
    assert frontend_events.json()["events"][0]["behavior_id"] == "pick_and_place"

    dispatch = client.post(f"/api/simulation-runs/{run_id}/device-tasks/dispatch", json={"sim_time_s": 1.6})
    assert dispatch.status_code == 200
    assert dispatch.json()["dispatched_actions"][0]["instance_id"] == "robot_1"
    assert dispatch.json()["snapshot"]["device_states"]["robot_1"] == "busy"

    action_id = dispatch.json()["dispatched_actions"][0]["action_id"]
    complete = client.post(f"/api/simulation-runs/{run_id}/actions/{action_id}/complete", json={"sim_time_s": 2.4, "payload": {"completed_by": "frontend"}})
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed_active_action"
    assert complete.json()["snapshot"]["device_states"]["robot_1"] == "idle"
    assert action_id not in complete.json()["snapshot"]["active_actions"]

    snapshot = client.put(f"/api/simulation-runs/{run_id}/runtime-snapshot", json={"snapshot": {"clock": 2, "signal_values": {"conveyor_1.part_ready": True}}})
    assert snapshot.status_code == 200
    assert snapshot.json()["snapshot"]["clock"] == 2

    cleanup = client.delete(f"/api/simulation-runs/{run_id}/runtime-state")
    assert cleanup.status_code == 200
    assert cleanup.json()["cleared"] is True


def test_replace_scene_document_rebuilds_topology_and_bootstraps_startup_runtime() -> None:
    client = make_client()
    run_id = create_scene1_runtime(client)

    frontend_events = client.get(f"/api/simulation-runs/{run_id}/frontend-events")
    assert frontend_events.status_code == 200
    first_event = frontend_events.json()["events"][0]
    assert first_event["type"] == "device_behavior_triggered"
    assert first_event["instance_id"] == "main_conveyor_1"
    assert first_event["behavior_id"] == "transport_to_exit"
    assert first_event["payload"]["from_point_id"] == "main_conveyor_1.sp_01"
    assert first_event["payload"]["to_point_id"] == "main_conveyor_1.sp_02"
    assert first_event["payload"]["runtime_geometry"]["transport_path"]["waypoints"][0] == [2.619, 0.15, -1.197]

    first_complete = client.post(
        f"/api/simulation-runs/{run_id}/actions/{first_event['task_id']}/complete",
        json={"sim_time_s": 1.4, "payload": {"completed_by": "frontend"}},
    )
    assert first_complete.status_code == 200
    first_complete_body = first_complete.json()
    assert first_complete_body["snapshot"]["conveyor_occupancy"]["main_conveyor_1"]["main_conveyor_1.sp_01"] is None
    assert first_complete_body["snapshot"]["conveyor_occupancy"]["main_conveyor_1"]["main_conveyor_1.sp_02"] == "pallet_1"
    followup_event = first_complete_body["runtime_followup_frontend_events"][0]
    assert followup_event["instance_id"] == "main_conveyor_1"
    assert followup_event["behavior_id"] == "advance_to_next_stop_point"
    assert followup_event["payload"]["from_point_id"] == "main_conveyor_1.sp_02"
    assert followup_event["payload"]["to_point_id"] == "main_conveyor_1.sp_03"


def test_scene_document_runtime_reaches_robot_claim_loop() -> None:
    client = make_client()
    run_id = create_scene1_runtime(client)
    seen_task_ids: set[str] = set()
    completed_task_ids: set[str] = set()
    robot_pick_events: list[dict] = []
    last_completion: dict | None = None

    for step in range(12):
        event = next_frontend_event(client, run_id, seen_task_ids)
        seen_task_ids.add(event["task_id"])
        if event["behavior_id"] == "pick_and_place":
            robot_pick_events.append(event)
            if len(robot_pick_events) == 2:
                break
            continue
        last_completion = complete_frontend_event(client, run_id, event, completed_task_ids, sim_time_s=float(step + 1))

    assert [event["instance_id"] for event in robot_pick_events] == ["robot_1", "robot_2"]
    assert [event["payload"]["material_id"] for event in robot_pick_events] == ["part_001", "part_002"]
    assert [event["payload"]["target_conveyor_id"] for event in robot_pick_events] == ["upper_out_conveyor_1", "lower_out_conveyor_1"]
    assert robot_pick_events[0]["payload"]["subject_id"] == "part_001"
    assert last_completion is not None
    assert last_completion["snapshot"]["conveyor_occupancy"]["main_conveyor_2"]["main_conveyor_2.sp_04"] == "pallet_1"

    first_robot_complete = complete_frontend_event(client, run_id, robot_pick_events[0], completed_task_ids, sim_time_s=20.0)
    assert first_robot_complete["process_handoff_frontend_events"][0]["instance_id"] == "upper_out_conveyor_1"
    assert first_robot_complete["process_handoff_frontend_events"][0]["behavior_id"] == "accept_material"
    assert first_robot_complete["process_handoff_frontend_events"][0]["payload"]["material_id"] == "part_001"
    assert first_robot_complete["robot_followup_frontend_events"][0]["instance_id"] == "robot_1"
    assert first_robot_complete["robot_followup_frontend_events"][0]["payload"]["material_id"] == "part_003"


def test_supabase_migration_contains_required_runtime_and_agent_tables() -> None:
    migration = Path("supabase/migrations/20260906190000_initial_backend_schema.sql").read_text(encoding="utf-8")
    for table in ["projects", "assets", "device_specs", "scenes", "scene_events", "scene_topologies", "simulation_runs", "simulation_events", "agent_runs", "agent_artifacts", "agent_events"]:
        assert f"public.{table}" in migration
    assert "agent_threads" not in migration
