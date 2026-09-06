from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.db import models
from app.repositories.sql import ProjectRepository, SceneRepository, SimulationRepository
from app.schemas.domain import RuntimeSnapshotPut, SignalEmitRequest, SimulationRunCreate
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore


class SimulationService:
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.scenes = SceneRepository(db)
        self.simulations = SimulationRepository(db)
        self.runtime_store = runtime_store

    def create_run(self, project_id: str, payload: SimulationRunCreate) -> models.SimulationRun:
        if not self.projects.get(project_id):
            raise NotFoundError("Project", project_id)
        scene = self.scenes.get_by_project(project_id)
        if not scene:
            raise NotFoundError("Scene", project_id)
        if payload.base_scene_revision is not None and payload.base_scene_revision != scene.revision:
            raise AppError("SCENE_REVISION_CONFLICT", "Simulation run base revision does not match current scene revision.", 409, {"expected_revision": payload.base_scene_revision, "current_revision": scene.revision})
        run_id = new_id("simrun")
        snapshot = payload.initial_snapshot or self._initial_snapshot(scene)
        snapshot["run_id"] = run_id
        run = models.SimulationRun(
            id=run_id,
            project_id=project_id,
            scene_id=scene.id,
            base_scene_revision=scene.revision,
            status="created",
            runtime_snapshot=snapshot,
        )
        self.simulations.add_run(run)
        self.db.commit()
        self.runtime_store.put_snapshot(run.id, snapshot)
        return run

    def get_run(self, run_id: str) -> models.SimulationRun:
        run = self.simulations.get_run(run_id)
        if not run:
            raise NotFoundError("SimulationRun", run_id)
        return run

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        self.get_run(run_id)
        return self.runtime_store.get_snapshot(run_id)

    def put_snapshot(self, run_id: str, payload: RuntimeSnapshotPut) -> dict[str, Any]:
        run = self.get_run(run_id)
        run.runtime_snapshot = payload.snapshot
        self.db.commit()
        self.runtime_store.put_snapshot(run_id, payload.snapshot, payload.ttl_seconds)
        return payload.snapshot

    def emit_signal(self, run_id: str, signal_id: str, payload: SignalEmitRequest) -> dict[str, Any]:
        self.get_run(run_id)
        event = self.runtime_store.set_signal(run_id, signal_id, payload.value, payload.payload, payload.ttl_seconds)
        self.simulations.add_event(models.SimulationEvent(id=new_id("simevt"), simulation_run_id=run_id, sim_time_s=payload.sim_time_s, event_type="signal_event", payload=event))
        self.db.commit()
        return event

    def clear_runtime_state(self, run_id: str) -> dict[str, Any]:
        self.get_run(run_id)
        self.runtime_store.clear_run(run_id)
        return {"run_id": run_id, "cleared": True}

    @staticmethod
    def _initial_snapshot(scene: models.Scene) -> dict[str, Any]:
        document = scene.current_document
        return {
            "schema_type": "RuntimeSnapshot",
            "version": "0.2.0",
            "run_id": None,
            "clock": 0,
            "topology_graph_ref": document.get("derived_artifacts", {}).get("topology_graph", {}),
            "signal_values": {},
            "event_queue": [],
            "device_states": {instance.get("instance_id"): "idle" for instance in document.get("instances", [])},
            "material_locations": {item.get("material_id"): item.get("located_at") for item in document.get("materials", [])},
            "resource_locks": {},
            "active_actions": {},
        }
