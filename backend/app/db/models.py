from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    scenes: Mapped[list["Scene"]] = relationship(back_populates="project")


class Asset(TimestampMixin, Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="supabase", nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(255))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)


class DeviceSpec(TimestampMixin, Base):
    __tablename__ = "device_specs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    spec_key: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    device_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document: Mapped[dict] = mapped_column(JSON, nullable=False)


class Scene(TimestampMixin, Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), index=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), default="scene/v0.2", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_document: Mapped[dict] = mapped_column(JSON, nullable=False)

    project: Mapped[Project] = relationship(back_populates="scenes")


class SceneEvent(TimestampMixin, Base):
    __tablename__ = "scene_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenes.id"), index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class SceneTopology(TimestampMixin, Base):
    __tablename__ = "scene_topologies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenes.id"), index=True, nullable=False)
    scene_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    graph_hash: Mapped[str | None] = mapped_column(String(128))
    document: Mapped[dict] = mapped_column(JSON, nullable=False)


class SimulationRun(TimestampMixin, Base):
    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), index=True, nullable=False)
    scene_id: Mapped[str] = mapped_column(String(64), ForeignKey("scenes.id"), index=True, nullable=False)
    base_scene_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="created", nullable=False)
    runtime_snapshot: Mapped[dict | None] = mapped_column(JSON)
    metrics_summary: Mapped[dict | None] = mapped_column(JSON)


class SimulationEvent(TimestampMixin, Base):
    __tablename__ = "simulation_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    simulation_run_id: Mapped[str] = mapped_column(String(64), ForeignKey("simulation_runs.id"), index=True, nullable=False)
    sim_time_s: Mapped[float | None] = mapped_column(Float)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)

