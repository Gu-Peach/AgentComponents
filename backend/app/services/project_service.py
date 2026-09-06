from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.db import models
from app.repositories.sql import ProjectRepository, SceneRepository
from app.schemas.domain import ProjectCreate
from app.services.ids import new_id


def default_scene_document(scene_id: str, project_id: str) -> dict:
    return {
        "schema_id": f"scene_document_{scene_id}_v0_2",
        "schema_type": "SceneDocument",
        "version": "0.2.0",
        "name": "Default SceneDocument",
        "description": "Project scene facts.",
        "source": {"kind": "backend_created"},
        "created_for": "scene authoring",
        "references": ["docs/business/SimulationSchema/2.SceneDocument/schema.json"],
        "notes": ["Runtime state is stored outside SceneDocument."],
        "scene_id": scene_id,
        "project_id": project_id,
        "revision": 0,
        "instances": [],
        "materials": [],
        "process_edges": [],
        "physical_edges": [],
        "signal_edges": [],
        "runtime_config": {"deadlock_detection": True, "default_signal_timeout_s": 30, "topology_rebuild_policy": "before_run"},
        "derived_artifacts": {"topology_graph": {"graph_id": None, "status": "not_built", "source_scene_revision": 0}},
    }


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.scenes = SceneRepository(db)

    def create(self, payload: ProjectCreate) -> models.Project:
        project = models.Project(id=new_id("project"), name=payload.name, description=payload.description)
        self.projects.add(project)
        scene_id = new_id("scene")
        self.scenes.add(
            models.Scene(
                id=scene_id,
                project_id=project.id,
                revision=0,
                current_document=default_scene_document(scene_id, project.id),
            )
        )
        self.db.commit()
        self.db.refresh(project)
        return project

    def list(self) -> list[models.Project]:
        return self.projects.list()

    def get(self, project_id: str) -> models.Project:
        project = self.projects.get(project_id)
        if not project:
            raise NotFoundError("Project", project_id)
        return project

