from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


JsonDict = dict[str, Any]


class Transform(BaseModel):
    position: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    rotation_euler: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0], min_length=3, max_length=3)
    scale: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0], min_length=3, max_length=3)


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None = None


class AssetCreate(BaseModel):
    bucket: str = Field(min_length=1)
    path: str = Field(min_length=1)
    provider: str = "supabase"
    mime_type: str | None = None
    size_bytes: int | None = None
    metadata: JsonDict = Field(default_factory=dict)


class AssetResponse(AssetCreate):
    asset_id: str


class DeviceSpecCreate(BaseModel):
    spec_id: str | None = None
    spec_key: str | None = None
    document: JsonDict


class DeviceSpecResponse(BaseModel):
    spec_id: str
    spec_key: str
    device_type: str
    version: str
    display_name: str
    document: JsonDict


class SceneResponse(BaseModel):
    scene_id: str
    project_id: str
    revision: int
    document: JsonDict


class RevisionedRequest(BaseModel):
    base_revision: int = Field(ge=0)


class InstanceCreate(RevisionedRequest):
    spec_id: str
    instance_id: str | None = None
    display_name: str | None = None
    device_type: str | None = None
    transform: Transform = Field(default_factory=Transform)
    param_overrides: JsonDict = Field(default_factory=dict)
    visible: bool = True
    locked: bool = False
    semantic_tags: list[str] = Field(default_factory=list)


class InstancePatch(RevisionedRequest):
    display_name: str | None = None
    transform: Transform | None = None
    param_overrides: JsonDict | None = None
    visible: bool | None = None
    locked: bool | None = None
    semantic_tags: list[str] | None = None


class InstanceDelete(RevisionedRequest):
    delete_policy: Literal["reject_if_connected", "delete_incident_edges", "stage_for_confirmation"] = "reject_if_connected"


class EdgeCreate(RevisionedRequest):
    source: str = Field(min_length=3)
    target: str = Field(min_length=3)
    edge_id: str | None = None
    edge_type: str = "material_flow"
    metadata: JsonDict = Field(default_factory=dict)


class SignalEdgeCreate(EdgeCreate):
    edge_type: str = "control_signal"
    delivery: Literal["event", "latest_value", "command", "broadcast"] = "event"
    trigger: Literal["on_rising_edge", "on_falling_edge", "on_change", "level", "manual"] = "on_rising_edge"
    transform: JsonDict = Field(default_factory=lambda: {"type": "identity"})
    timeout_ms: int = Field(default=30000, ge=0)
    on_timeout: Literal["raise_observation", "retry", "ignore", "pause_and_request_replan"] = "raise_observation"
    enabled: bool = True


class EdgeDelete(RevisionedRequest):
    pass


class CompileInterfacesRequest(RevisionedRequest):
    mode: Literal["dry_run", "apply"] = "dry_run"


class MutationResponse(BaseModel):
    scene_id: str
    previous_revision: int
    new_revision: int
    event_id: str
    document: JsonDict
    warnings: list[JsonDict] = Field(default_factory=list)


class TopologyResponse(BaseModel):
    topology_id: str | None = None
    scene_id: str
    scene_revision: int
    document: JsonDict


class SimulationRunCreate(BaseModel):
    base_scene_revision: int | None = None
    initial_snapshot: JsonDict | None = None


class SimulationRunResponse(BaseModel):
    run_id: str
    project_id: str
    scene_id: str
    base_scene_revision: int
    status: str
    runtime_snapshot: JsonDict | None = None


class RuntimeSnapshotPut(BaseModel):
    snapshot: JsonDict
    ttl_seconds: int | None = Field(default=None, ge=1)


class SignalEmitRequest(BaseModel):
    value: Any = None
    payload: JsonDict = Field(default_factory=dict)
    sim_time_s: float | None = None
    ttl_seconds: int | None = Field(default=None, ge=1)


class ValidationIssue(BaseModel):
    severity: Literal["info", "warning", "error"]
    code: str
    message: str
    path: str | None = None
    details: JsonDict = Field(default_factory=dict)

