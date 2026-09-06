from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.serializers import scene_response
from app.db.session import get_db
from app.schemas.domain import CompileInterfacesRequest, EdgeCreate, EdgeDelete, InstanceCreate, InstanceDelete, InstancePatch, MutationResponse, SceneResponse, SignalEdgeCreate, TopologyResponse
from app.services.scene_service import SceneService

router = APIRouter(prefix="/api/projects/{project_id}", tags=["scenes"])


@router.get("/scene", response_model=SceneResponse)
def get_scene(project_id: str, db: Session = Depends(get_db)) -> dict:
    return scene_response(SceneService(db).get_scene_for_project(project_id))


@router.post("/scene/instances", response_model=MutationResponse)
def add_instance(project_id: str, payload: InstanceCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).add_instance(project_id, payload)


@router.patch("/scene/instances/{instance_id}", response_model=MutationResponse)
def patch_instance(project_id: str, instance_id: str, payload: InstancePatch, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).patch_instance(project_id, instance_id, payload)


@router.delete("/scene/instances/{instance_id}", response_model=MutationResponse)
def delete_instance(project_id: str, instance_id: str, payload: InstanceDelete, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).delete_instance(project_id, instance_id, payload)


@router.get("/scene/{edge_kind}-edges")
def list_edges(project_id: str, edge_kind: Literal["process", "physical", "signal"], db: Session = Depends(get_db)) -> list[dict]:
    return SceneService(db).list_edges(project_id, edge_kind)


@router.post("/scene/process-edges", response_model=MutationResponse)
def create_process_edge(project_id: str, payload: EdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "process", payload)


@router.post("/scene/physical-edges", response_model=MutationResponse)
def create_physical_edge(project_id: str, payload: EdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "physical", payload)


@router.post("/scene/signal-edges", response_model=MutationResponse)
def create_signal_edge(project_id: str, payload: SignalEdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "signal", payload)


@router.delete("/scene/{edge_kind}-edges/{edge_id}", response_model=MutationResponse)
def delete_edge(project_id: str, edge_kind: Literal["process", "physical", "signal"], edge_id: str, payload: EdgeDelete, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).delete_edge(project_id, edge_kind, edge_id, payload)


@router.post("/interfaces/compile")
def compile_interfaces(project_id: str, payload: CompileInterfacesRequest, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).compile_interfaces(project_id, payload)


@router.post("/topology/rebuild", response_model=TopologyResponse)
def rebuild_topology(project_id: str, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).rebuild_topology(project_id)


@router.get("/topology", response_model=TopologyResponse)
def get_topology(project_id: str, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).get_latest_topology(project_id)


@router.get("/topology/reachability")
def get_reachability(project_id: str, source: str, target: str, graph: str = Query(default="process_graph"), db: Session = Depends(get_db)) -> dict:
    return SceneService(db).reachability(project_id, source, target, graph)

