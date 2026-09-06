from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, project: models.Project) -> models.Project:
        self.db.add(project)
        return project

    def get(self, project_id: str) -> models.Project | None:
        return self.db.get(models.Project, project_id)

    def list(self) -> list[models.Project]:
        return list(self.db.scalars(select(models.Project).order_by(models.Project.created_at.desc())))


class DeviceSpecRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, spec: models.DeviceSpec) -> models.DeviceSpec:
        existing = self.get(spec.id) or self.get_by_key(spec.spec_key)
        if existing:
            existing.spec_key = spec.spec_key
            existing.device_type = spec.device_type
            existing.version = spec.version
            existing.display_name = spec.display_name
            existing.document = spec.document
            return existing
        self.db.add(spec)
        return spec

    def get(self, spec_id: str) -> models.DeviceSpec | None:
        return self.db.get(models.DeviceSpec, spec_id)

    def get_by_key(self, spec_key: str) -> models.DeviceSpec | None:
        stmt = select(models.DeviceSpec).where(models.DeviceSpec.spec_key == spec_key)
        return self.db.scalar(stmt)

    def list(self, device_type: str | None = None) -> list[models.DeviceSpec]:
        stmt = select(models.DeviceSpec).order_by(models.DeviceSpec.device_type, models.DeviceSpec.spec_key)
        if device_type:
            stmt = stmt.where(models.DeviceSpec.device_type == device_type)
        return list(self.db.scalars(stmt))


class AssetRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, asset: models.Asset) -> models.Asset:
        self.db.add(asset)
        return asset

    def get(self, asset_id: str) -> models.Asset | None:
        return self.db.get(models.Asset, asset_id)

    def list(self) -> list[models.Asset]:
        return list(self.db.scalars(select(models.Asset).order_by(models.Asset.created_at.desc())))


class SceneRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, scene: models.Scene) -> models.Scene:
        self.db.add(scene)
        return scene

    def get(self, scene_id: str) -> models.Scene | None:
        return self.db.get(models.Scene, scene_id)

    def get_by_project(self, project_id: str) -> models.Scene | None:
        stmt = select(models.Scene).where(models.Scene.project_id == project_id).order_by(models.Scene.created_at.asc())
        return self.db.scalar(stmt)

    def add_event(self, event: models.SceneEvent) -> models.SceneEvent:
        self.db.add(event)
        return event

    def save_topology(self, topology: models.SceneTopology) -> models.SceneTopology:
        self.db.add(topology)
        return topology

    def latest_topology(self, scene_id: str) -> models.SceneTopology | None:
        stmt = select(models.SceneTopology).where(models.SceneTopology.scene_id == scene_id).order_by(models.SceneTopology.scene_revision.desc(), models.SceneTopology.created_at.desc())
        return self.db.scalar(stmt)


class SimulationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add_run(self, run: models.SimulationRun) -> models.SimulationRun:
        self.db.add(run)
        return run

    def get_run(self, run_id: str) -> models.SimulationRun | None:
        return self.db.get(models.SimulationRun, run_id)

    def add_event(self, event: models.SimulationEvent) -> models.SimulationEvent:
        self.db.add(event)
        return event

