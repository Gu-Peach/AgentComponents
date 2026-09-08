from __future__ import annotations

from pathlib import Path

from conftest import make_client


def test_project_scene_edges_compile_topology_and_runtime() -> None:
    client = make_client()
    assert client.get("/health").json()["agent_enabled"] is False

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


def test_supabase_migration_contains_required_tables_and_no_agent_tables() -> None:
    migration = Path("supabase/migrations/20260906190000_initial_backend_schema.sql").read_text(encoding="utf-8")
    for table in ["projects", "assets", "device_specs", "scenes", "scene_events", "scene_topologies", "simulation_runs", "simulation_events"]:
        assert f"public.{table}" in migration
    assert "agent_runs" not in migration
    assert "agent_threads" not in migration
