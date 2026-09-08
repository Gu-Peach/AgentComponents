from __future__ import annotations

from collections import Counter

from sqlalchemy import select

from app.db import models
from app.db.session import SessionLocal
from app.schemas.domain import ActionCompleteRequest, DeviceTaskDispatchRequest, InstanceCreate, ProjectCreate, SignalEdgeCreate, SignalEmitRequest, SimulationRunCreate
from app.services.catalog_service import DeviceSpecService
from app.services.project_service import ProjectService
from app.services.runtime_state import InMemoryRuntimeStateStore
from app.services.scene_service import SceneService
from app.services.simulation_service import SimulationService


def _db_events(db, run_id: str) -> list[models.SimulationEvent]:
    stmt = (
        select(models.SimulationEvent)
        .where(models.SimulationEvent.simulation_run_id == run_id)
        .order_by(models.SimulationEvent.created_at)
    )
    return list(db.scalars(stmt))


def _create_run_with_signal_edges(edges: list[dict]) -> tuple:
    db = SessionLocal()
    store = InMemoryRuntimeStateStore()
    DeviceSpecService(db).import_defaults()
    project = ProjectService(db).create(ProjectCreate(name="Signal bus test"))
    scene_service = SceneService(db)

    revision = 0
    scene_service.add_instance(project.id, InstanceCreate(base_revision=revision, spec_id="conveyor_1", instance_id="conveyor_1"))
    revision += 1
    scene_service.add_instance(project.id, InstanceCreate(base_revision=revision, spec_id="robot_arm_1", instance_id="robot_1"))
    revision += 1

    if any(edge["target"].startswith("robot_2.") for edge in edges):
        scene_service.add_instance(project.id, InstanceCreate(base_revision=revision, spec_id="robot_arm_1", instance_id="robot_2"))
        revision += 1

    for edge in edges:
        scene_service.create_edge(
            project.id,
            "signal",
            SignalEdgeCreate(
                base_revision=revision,
                edge_id=edge.get("edge_id"),
                source=edge.get("source", "conveyor_1.part_ready"),
                target=edge["target"],
                enabled=edge.get("enabled", True),
                delivery=edge.get("delivery", "event"),
                trigger=edge.get("trigger", "on_rising_edge"),
                transform=edge.get("transform", {"type": "identity"}),
                metadata={"route_id": edge.get("route_id")} if edge.get("route_id") else {},
            ),
        )
        revision += 1

    simulation = SimulationService(db, store)
    run = simulation.create_run(project.id, SimulationRunCreate())
    return db, store, simulation, run


def test_emit_without_consumers_records_only_source_signal() -> None:
    db, store, simulation, run = _create_run_with_signal_edges([])
    try:
        result = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}, sim_time_s=1.0),
        )

        assert result["signal_id"] == "conveyor_1.part_ready"
        assert result["routed_events"] == []
        assert result["device_tasks"] == []
        assert store.get_signals(run.id)["conveyor_1.part_ready"]["value"] is True
        assert [event["type"] for event in store.get_events(run.id)] == ["signal_event"]
        assert [event.event_type for event in _db_events(db, run.id)] == ["signal_event"]
    finally:
        db.close()


def test_emit_routes_to_one_consumer_and_creates_pending_device_task() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [
            {
                "edge_id": "sig_conveyor_to_robot",
                "target": "robot_1.start_pick",
                "route_id": "route_conveyor_to_robot",
            }
        ]
    )
    try:
        result = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}, sim_time_s=2.0),
        )

        assert result["signal_id"] == "conveyor_1.part_ready"
        assert result["route_source"] == "topology_graph"
        assert len(result["routed_events"]) == 1
        assert result["routed_events"][0]["signal_id"] == "robot_1.start_pick"
        assert result["routed_events"][0]["value"] is True
        assert result["routed_events"][0]["payload"] == {"material_id": "part_001"}
        assert store.get_signals(run.id)["robot_1.start_pick"]["value"] is True

        assert len(result["device_tasks"]) == 1
        task = result["device_tasks"][0]
        assert task["instance_id"] == "robot_1"
        assert task["signal_port"] == "start_pick"
        assert task["behavior_id"] == "pick_and_place"
        assert task["status"] == "pending"
        assert store.get_device_tasks(run.id)[0]["task_id"] == task["task_id"]

        assert len(result["frontend_events"]) == 1
        frontend_event = result["frontend_events"][0]
        assert frontend_event["type"] == "device_behavior_triggered"
        assert frontend_event["task_id"] == task["task_id"]
        assert frontend_event["instance_id"] == "robot_1"
        assert frontend_event["behavior_id"] == "pick_and_place"
        assert frontend_event["payload"] == {"material_id": "part_001"}
        assert frontend_event["sequence"] == 1
        assert store.get_frontend_events(run.id)[0]["event_id"] == frontend_event["event_id"]

        snapshot = store.get_snapshot(run.id)
        assert snapshot["signal_values"]["robot_1.start_pick"] is True
        assert snapshot["device_fsm_states"]["robot_1"] == "queued"
        assert snapshot["frontend_events"][0]["task_id"] == task["task_id"]
        assert len(snapshot["event_queue"]) == 2

        event_types = Counter(event.event_type for event in _db_events(db, run.id))
        assert event_types["signal_event"] == 1
        assert event_types["routed_signal_event"] == 1
        assert event_types["device_task_created"] == 1
        assert event_types["device_behavior_triggered"] == 1
    finally:
        db.close()


def test_emit_falls_back_to_scene_edges_when_topology_is_stale() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [
            {
                "edge_id": "sig_conveyor_to_robot",
                "target": "robot_1.start_pick",
                "route_id": "route_conveyor_to_robot",
            }
        ]
    )
    try:
        topology = simulation.scenes.latest_topology(run.scene_id)
        assert topology is not None
        topology.scene_revision = run.base_scene_revision - 1
        db.commit()

        result = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}, sim_time_s=2.0),
        )

        assert result["route_source"] == "scene_document"
        assert len(result["device_tasks"]) == 1
        assert result["device_tasks"][0]["instance_id"] == "robot_1"
    finally:
        db.close()


def test_dispatch_pending_device_task_starts_active_action() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [
            {
                "edge_id": "sig_conveyor_to_robot",
                "target": "robot_1.start_pick",
                "route_id": "route_conveyor_to_robot",
            }
        ]
    )
    try:
        emitted = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}, sim_time_s=2.0),
        )
        task_id = emitted["device_tasks"][0]["task_id"]

        result = simulation.dispatch_device_tasks(run.id, DeviceTaskDispatchRequest(sim_time_s=2.1))

        assert len(result["consumed_events"]) == 1
        assert result["consumed_events"][0]["status"] == "consumed"
        assert len(result["dispatched_actions"]) == 1
        action = result["dispatched_actions"][0]
        assert action["task_id"] == task_id
        assert action["instance_id"] == "robot_1"
        assert action["behavior_id"] == "pick_and_place"

        snapshot = store.get_snapshot(run.id)
        assert snapshot["device_tasks"][0]["status"] == "running"
        assert snapshot["device_states"]["robot_1"] == "busy"
        assert snapshot["device_fsm_states"]["robot_1"] == "busy"
        assert action["action_id"] in snapshot["active_actions"]
        assert any(event["type"] == "routed_signal_event" and event["status"] == "consumed" for event in snapshot["event_queue"])
        assert any(event["type"] == "device_action_started" for event in snapshot["event_queue"])
        assert any(event.event_type == "device_action_started" for event in _db_events(db, run.id))
    finally:
        db.close()


def test_complete_frontend_device_task_marks_runtime_done() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [
            {
                "edge_id": "sig_conveyor_to_robot",
                "target": "robot_1.start_pick",
                "route_id": "route_conveyor_to_robot",
            }
        ]
    )
    try:
        emitted = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}, sim_time_s=2.0),
        )
        task_id = emitted["device_tasks"][0]["task_id"]

        result = simulation.complete_action(
            run.id,
            task_id,
            ActionCompleteRequest(sim_time_s=3.0, payload={"completed_by": "frontend"}),
        )

        assert result["status"] == "completed_device_task"
        assert result["completed_task"]["status"] == "done"
        assert result["completed_task"]["completion_payload"] == {"completed_by": "frontend"}

        snapshot = store.get_snapshot(run.id)
        assert snapshot["device_tasks"][0]["status"] == "done"
        assert snapshot["device_states"]["robot_1"] == "idle"
        assert snapshot["device_fsm_states"]["robot_1"] == "idle"
        assert snapshot["frontend_events"][0]["status"] == "done"
        assert any(event["type"] == "device_action_completed" and event["task_id"] == task_id for event in snapshot["event_queue"])
        assert any(event.event_type == "device_action_completed" for event in _db_events(db, run.id))
    finally:
        db.close()


def test_emit_fans_out_to_multiple_consumers() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [
            {"edge_id": "sig_to_robot_1", "target": "robot_1.start_pick"},
            {"edge_id": "sig_to_robot_2", "target": "robot_2.start_pick"},
        ]
    )
    try:
        result = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"batch_id": "b001"}, sim_time_s=3.0),
        )

        assert {event["signal_id"] for event in result["routed_events"]} == {"robot_1.start_pick", "robot_2.start_pick"}
        assert {task["instance_id"] for task in result["device_tasks"]} == {"robot_1", "robot_2"}
        assert {event["instance_id"] for event in result["frontend_events"]} == {"robot_1", "robot_2"}
        assert [event["sequence"] for event in result["frontend_events"]] == [1, 2]
        signals = store.get_signals(run.id)
        assert signals["robot_1.start_pick"]["payload"] == {"batch_id": "b001"}
        assert signals["robot_2.start_pick"]["payload"] == {"batch_id": "b001"}
        assert len([event for event in store.get_events(run.id) if event["type"] == "routed_signal_event"]) == 2
    finally:
        db.close()


def test_disabled_signal_edge_is_not_delivered() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [{"edge_id": "sig_disabled", "target": "robot_1.start_pick", "enabled": False}]
    )
    try:
        result = simulation.emit_signal(
            run.id,
            "conveyor_1.part_ready",
            SignalEmitRequest(value=True, payload={"material_id": "part_001"}),
        )

        assert result["routed_events"] == []
        assert result["device_tasks"] == []
        assert "robot_1.start_pick" not in store.get_signals(run.id)
        assert [event.event_type for event in _db_events(db, run.id)] == ["signal_event"]
    finally:
        db.close()


def test_identity_transform_preserves_value_and_payload() -> None:
    db, store, simulation, run = _create_run_with_signal_edges(
        [{"edge_id": "sig_identity", "target": "robot_1.start_pick", "transform": {"type": "identity"}}]
    )
    try:
        payload = {"material_id": "part_001", "priority": 5}
        result = simulation.emit_signal(run.id, "conveyor_1.part_ready", SignalEmitRequest(value=True, payload=payload))

        routed = result["routed_events"][0]
        assert routed["value"] is True
        assert routed["payload"] == payload
        assert store.get_signals(run.id)["robot_1.start_pick"]["payload"] == payload
    finally:
        db.close()
