from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.serializers import scene_response
from app.db.session import get_db
from app.schemas.domain import CompileInterfacesRequest, EdgeCreate, EdgeDelete, InstanceCreate, InstanceDelete, InstancePatch, MutationResponse, SceneResponse, SignalEdgeCreate, TopologyResponse
from app.services.scene_service import SceneService

router = APIRouter(prefix="/api/projects/{project_id}", tags=["scenes"])


# 获取项目场景：GET /api/projects/{project_id}/scene，返回该项目当前场景文档。
@router.get("/scene", response_model=SceneResponse)
def get_scene(project_id: str, db: Session = Depends(get_db)) -> dict:
    return scene_response(SceneService(db).get_scene_for_project(project_id))


# 添加设备实例：POST /api/projects/{project_id}/scene/instances，向场景中新增一个设备实例。
@router.post("/scene/instances", response_model=MutationResponse)
def add_instance(project_id: str, payload: InstanceCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).add_instance(project_id, payload)


# 修改设备实例：PATCH /api/projects/{project_id}/scene/instances/{instance_id}，按 instance_id 更新实例属性。
@router.patch("/scene/instances/{instance_id}", response_model=MutationResponse)
def patch_instance(project_id: str, instance_id: str, payload: InstancePatch, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).patch_instance(project_id, instance_id, payload)


# 删除设备实例：DELETE /api/projects/{project_id}/scene/instances/{instance_id}，按删除策略移除实例。
@router.delete("/scene/instances/{instance_id}", response_model=MutationResponse)
def delete_instance(project_id: str, instance_id: str, payload: InstanceDelete, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).delete_instance(project_id, instance_id, payload)


# 查询边列表：GET /api/projects/{project_id}/scene/{edge_kind}-edges，按边类型查询流程/物理/信号边。
@router.get("/scene/{edge_kind}-edges")
def list_edges(project_id: str, edge_kind: Literal["process", "physical", "signal"], db: Session = Depends(get_db)) -> list[dict]:
    return SceneService(db).list_edges(project_id, edge_kind)


# 创建流程边：POST /api/projects/{project_id}/scene/process-edges，建立流程关系连接。
@router.post("/scene/process-edges", response_model=MutationResponse)
def create_process_edge(project_id: str, payload: EdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "process", payload)


# 创建物理边：POST /api/projects/{project_id}/scene/physical-edges，建立物理接口连接。
@router.post("/scene/physical-edges", response_model=MutationResponse)
def create_physical_edge(project_id: str, payload: EdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "physical", payload)


# 创建信号边：POST /api/projects/{project_id}/scene/signal-edges，建立控制信号连接。
@router.post("/scene/signal-edges", response_model=MutationResponse)
def create_signal_edge(project_id: str, payload: SignalEdgeCreate, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).create_edge(project_id, "signal", payload)


# 删除边：DELETE /api/projects/{project_id}/scene/{edge_kind}-edges/{edge_id}，按边类型和 edge_id 删除连接。
@router.delete("/scene/{edge_kind}-edges/{edge_id}", response_model=MutationResponse)
def delete_edge(project_id: str, edge_kind: Literal["process", "physical", "signal"], edge_id: str, payload: EdgeDelete, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).delete_edge(project_id, edge_kind, edge_id, payload)


# 编译接口：POST /api/projects/{project_id}/interfaces/compile，检查或应用场景中的接口绑定关系。
@router.post("/interfaces/compile")
def compile_interfaces(project_id: str, payload: CompileInterfacesRequest, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).compile_interfaces(project_id, payload)


# 重建拓扑：POST /api/projects/{project_id}/topology/rebuild，根据当前场景重新生成拓扑图。
@router.post("/topology/rebuild", response_model=TopologyResponse)
def rebuild_topology(project_id: str, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).rebuild_topology(project_id)


# 获取拓扑：GET /api/projects/{project_id}/topology，返回该项目最新拓扑图。
@router.get("/topology", response_model=TopologyResponse)
def get_topology(project_id: str, db: Session = Depends(get_db)) -> dict:
    return SceneService(db).get_latest_topology(project_id)


# 判断可达性：GET /api/projects/{project_id}/topology/reachability，判断指定图中 source 到 target 是否连通。
@router.get("/topology/reachability")
def get_reachability(project_id: str, source: str, target: str, graph: str = Query(default="process_graph"), db: Session = Depends(get_db)) -> dict:
    return SceneService(db).reachability(project_id, source, target, graph)

