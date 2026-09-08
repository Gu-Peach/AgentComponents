from __future__ import annotations

from app.agent.compiler import BehaviorClosureValidator, IntentSchemaTool, ProcessTemplateLibrary, RuntimePreflightValidator
from app.agent.contracts import ArtifactSchemaValidator, PatchEnvelope, SchemaContractRegistry
from app.agent.documents import DocumentParser, DocumentReader, DocumentPatchWriter, UnitNormalizer
from conftest import make_client


def _project_with_conveyor_robot(process_edge: bool = True) -> tuple[object, str, int]:
    client = make_client()
    assert client.post("/api/device-specs/import-defaults").status_code == 200
    project = client.post("/api/projects", json={"name": "Agent test line"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    assert client.post(
        f"/api/projects/{project_id}/scene/instances",
        json={"base_revision": 0, "spec_id": "conveyor_1", "instance_id": "conveyor_1", "transform": {"position": [0, 0, 0], "rotation_euler": [0, 0, 0], "scale": [1, 1, 1]}},
    ).status_code == 200
    assert client.post(
        f"/api/projects/{project_id}/scene/instances",
        json={"base_revision": 1, "spec_id": "robot_arm_1", "instance_id": "robot_1", "transform": {"position": [0.35, 0, 0], "rotation_euler": [0, 0, 0], "scale": [1, 1, 1]}},
    ).status_code == 200
    revision = 2
    if process_edge:
        edge = client.post(
            f"/api/projects/{project_id}/scene/process-edges",
            json={"base_revision": revision, "edge_id": "proc_conveyor_to_robot", "source": "conveyor_1.flow_output", "target": "robot_1.flow_input", "edge_type": "material_flow"},
        )
        assert edge.status_code == 200
        revision = edge.json()["new_revision"]
    return client, project_id, revision


def test_agent_contract_registry_and_artifact_validator() -> None:
    client = make_client()
    contracts = client.get("/api/agent/contracts")
    assert contracts.status_code == 200
    assert "scene_behavior_graph_patch" in contracts.json()["artifact_types"]
    graph = client.get("/api/agent/graph")
    assert graph.status_code == 200
    assert graph.json()["nodes"][0]["name"] == "LoadContextNode"

    registry = SchemaContractRegistry()
    assert {"AgentState", "AgentArtifact", "PatchEnvelope", "ValidationReport"} <= set(registry.list_contracts())

    envelope = PatchEnvelope(
        artifact_type="signal_patch",
        base_scene_revision=3,
        operations=[{"op": "add", "path": "/signal_edges/-", "value": {"edge_id": "sig_1"}}],
        reason="test",
        confidence=0.8,
        approval_required=False,
    )
    report = ArtifactSchemaValidator().validate_payload("signal_patch", envelope.model_dump(mode="json"))
    assert report.valid is True

    bad = ArtifactSchemaValidator().validate_payload("unknown", {})
    assert bad.valid is False
    assert bad.issues[0].code == "UNKNOWN_ARTIFACT_TYPE"


def test_agent_run_stages_behavior_graph_and_replayable_events() -> None:
    client, project_id, revision = _project_with_conveyor_robot(process_edge=True)

    run = client.post(
        f"/api/projects/{project_id}/agent-runs",
        json={"user_message": "传送带末端有料时，让空闲机器人抓到 A2 格", "base_scene_revision": revision},
    )
    assert run.status_code == 200
    body = run.json()
    assert body["status"] == "completed"
    assert body["intent"]["intent_type"] == "behavior_graph"
    assert body["checkpoint"]["current_node"] == "EmitResultNode"
    assert body["final_response"]["patch_artifact_count"] >= 1

    events = client.get(f"/api/agent-runs/{body['agent_run_id']}/events").json()
    event_types = [event["event_type"] for event in events]
    assert event_types[:2] == ["agent.run_created", "agent.scene_loaded"]
    assert "agent.device_specs_loaded" in event_types
    assert "agent.behavior_graph_created" in event_types
    assert "agent.finalized" in event_types

    artifacts = client.get(f"/api/agent-runs/{body['agent_run_id']}/artifacts").json()
    artifact_types = {artifact["artifact_type"] for artifact in artifacts}
    assert "diagnostic_report" in artifact_types
    assert "scene_behavior_graph_patch" in artifact_types
    behavior_patch = next(artifact for artifact in artifacts if artifact["artifact_type"] == "scene_behavior_graph_patch")
    assert behavior_patch["validation_report"]["valid"] is True
    assert behavior_patch["payload"]["base_scene_revision"] == revision
    graph = behavior_patch["payload"]["operations"][0]["value"]["graph"]
    assert BehaviorClosureValidator().validate(graph).valid is True
    assert RuntimePreflightValidator().validate(graph).valid is True


def test_agent_completes_position_only_topology_and_blocks_stale_patch_apply() -> None:
    client, project_id, revision = _project_with_conveyor_robot(process_edge=False)

    run = client.post(
        f"/api/projects/{project_id}/agent-runs",
        json={"user_message": "这个场景只有位置，请补齐拓扑、工艺连线和信号路由", "base_scene_revision": revision},
    )
    assert run.status_code == 200
    agent_run_id = run.json()["agent_run_id"]
    artifacts = client.get(f"/api/agent-runs/{agent_run_id}/artifacts").json()
    artifact_types = {artifact["artifact_type"] for artifact in artifacts}
    assert {"physical_edge_patch", "process_patch", "signal_patch"} <= artifact_types

    safe_patch = next(artifact for artifact in artifacts if artifact["artifact_type"] == "signal_patch")
    stale = client.post(f"/api/agent-runs/{agent_run_id}/artifacts/{safe_patch['artifact_id']}/apply", json={"expected_base_revision": revision + 1, "approved_by_user": True})
    assert stale.status_code == 409
    assert stale.json()["error"] == "SCENE_REVISION_CONFLICT"


def test_agent_extracts_parameters_and_stages_binding_patch() -> None:
    client, project_id, revision = _project_with_conveyor_robot(process_edge=True)

    run = client.post(
        f"/api/projects/{project_id}/agent-runs",
        json={"user_message": "把 process time = 45s，speed = 0.5 m/s，capacity = 4 绑定到当前场景参数", "base_scene_revision": revision},
    )
    assert run.status_code == 200
    artifacts = client.get(f"/api/agent-runs/{run.json()['agent_run_id']}/artifacts").json()
    parameter_patch = next(artifact for artifact in artifacts if artifact["artifact_type"] == "parameter_binding_patch")
    assert parameter_patch["validation_report"]["valid"] is True
    plan = parameter_patch["payload"]["parameter_binding_plan"]
    assert {param["name"] for param in plan["extracted_params"]} >= {"process_time_s", "speed_mps", "capacity"}
    assert all(binding["target"]["path"].startswith("/instances/") for binding in plan["target_bindings"])


def test_document_tools_parse_bindable_text_and_create_document_patch() -> None:
    document = DocumentReader().read(text="process time = 2 min\nspeed: 0.6 m/s")
    parsed = DocumentParser().parse(document["content"], document["mime_type"])
    assert parsed["key_value_candidates"][0]["key"] == "process time"
    normalized = UnitNormalizer().normalize([{"name": "process_time_s", "value": 2, "unit": "min"}])
    assert normalized[0]["value"] == 120
    patch = DocumentPatchWriter().create_patch("doc_1", 1, "补充：process_time_s=120")
    assert patch["operations"][0]["op"] == "append_text"
    assert IntentSchemaTool().parse("比较两个方案的产能")["intent_type"] == "scenario_compare"
    assert any(template["template_id"] == "robot_pick_place" for template in ProcessTemplateLibrary().list_templates())


def test_agent_diagnoses_runtime_missing_signal_route_and_plans_repair() -> None:
    client, project_id, revision = _project_with_conveyor_robot(process_edge=True)
    sim = client.post(f"/api/projects/{project_id}/simulation-runs", json={})
    assert sim.status_code == 200
    run_id = sim.json()["run_id"]
    snapshot = sim.json()["runtime_snapshot"]
    snapshot.setdefault("signal_values", {})["conveyor_1.part_ready"] = True
    snapshot.setdefault("event_queue", []).append({"type": "signal_event", "signal_id": "conveyor_1.part_ready", "status": "delivered"})
    assert client.put(f"/api/simulation-runs/{run_id}/runtime-snapshot", json={"snapshot": snapshot}).status_code == 200

    run = client.post(
        f"/api/projects/{project_id}/agent-runs",
        json={"user_message": "诊断为什么 conveyor_1.part_ready 没有触发机器人", "base_scene_revision": revision, "simulation_run_id": run_id},
    )
    assert run.status_code == 200
    artifacts = client.get(f"/api/agent-runs/{run.json()['agent_run_id']}/artifacts").json()
    diagnostic = next(artifact for artifact in artifacts if artifact["artifact_type"] == "diagnostic_report" and artifact["payload"].get("symptom") != "scene_context_loaded")
    assert diagnostic["payload"]["can_auto_repair"] is True
    assert diagnostic["payload"]["root_causes"][0]["cause_type"] == "missing_signal_route"
    assert any(artifact["artifact_type"] == "signal_patch" for artifact in artifacts)


def test_agent_creates_scenario_experiment_plan_with_two_variants() -> None:
    client, project_id, revision = _project_with_conveyor_robot(process_edge=True)

    run = client.post(
        f"/api/projects/{project_id}/agent-runs",
        json={"user_message": "比较两个方案的产能、WIP、瓶颈并给推荐", "base_scene_revision": revision, "scenario_count": 2},
    )
    assert run.status_code == 200
    artifacts = client.get(f"/api/agent-runs/{run.json()['agent_run_id']}/artifacts").json()
    scenario = next(artifact for artifact in artifacts if artifact["artifact_type"] == "scenario_experiment_plan")
    assert scenario["validation_report"]["valid"] is True
    assert len(scenario["payload"]["variants"]) == 2
    assert scenario["payload"]["metrics"]["requested"] == ["throughput", "cycle_time", "WIP", "waiting_time", "utilization", "blocked_time", "deadlock_count"]
    assert {assertion["metric"] for assertion in scenario["payload"]["assertions"]} >= {"throughput", "cycle_time", "WIP", "utilization", "timeout_rate"}
    assert scenario["payload"]["cannot_conclude"]
