from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.serializers import simulation_run_response
from app.db.session import get_db
from app.dependencies import get_runtime_store
from app.schemas.domain import DeviceTaskDispatchRequest, RuntimeSnapshotPut, SignalEmitRequest, SimulationRunCreate, SimulationRunResponse
from app.services.runtime_state import RuntimeStateStore
from app.services.simulation_service import SimulationService

router = APIRouter(tags=["simulation"])


# 创建仿真运行：POST /api/projects/{project_id}/simulation-runs，为指定项目启动一次仿真。
@router.post("/api/projects/{project_id}/simulation-runs", response_model=SimulationRunResponse)
def create_simulation_run(project_id: str, payload: SimulationRunCreate, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return simulation_run_response(SimulationService(db, runtime_store).create_run(project_id, payload))


# 查询仿真运行：GET /api/simulation-runs/{run_id}，按 run_id 返回仿真运行信息。
@router.get("/api/simulation-runs/{run_id}", response_model=SimulationRunResponse)
def get_simulation_run(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return simulation_run_response(SimulationService(db, runtime_store).get_run(run_id))


# 获取运行时快照：GET /api/simulation-runs/{run_id}/runtime-snapshot，返回当前仿真运行状态。
@router.get("/api/simulation-runs/{run_id}/runtime-snapshot")
def get_runtime_snapshot(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    snapshot = SimulationService(db, runtime_store).get_snapshot(run_id)
    return {"run_id": run_id, "snapshot": snapshot}


# 获取前端行为事件：GET /api/simulation-runs/{run_id}/frontend-events，返回设备动画可消费事件流。
@router.get("/api/simulation-runs/{run_id}/frontend-events")
def get_frontend_events(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    events = SimulationService(db, runtime_store).get_frontend_events(run_id)
    return {"run_id": run_id, "events": events}


# 写入运行时快照：PUT /api/simulation-runs/{run_id}/runtime-snapshot，保存或覆盖当前运行状态。
@router.put("/api/simulation-runs/{run_id}/runtime-snapshot")
def put_runtime_snapshot(run_id: str, payload: RuntimeSnapshotPut, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    snapshot = SimulationService(db, runtime_store).put_snapshot(run_id, payload)
    return {"run_id": run_id, "snapshot": snapshot}


# 发送仿真信号：POST /api/simulation-runs/{run_id}/signals/{signal_id}/emit，向指定运行发送信号事件或值。
@router.post("/api/simulation-runs/{run_id}/signals/{signal_id}/emit")
def emit_signal(run_id: str, signal_id: str, payload: SignalEmitRequest, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return SimulationService(db, runtime_store).emit_signal(run_id, signal_id, payload)


# 分发设备任务：POST /api/simulation-runs/{run_id}/device-tasks/dispatch，推进 pending task 为 active action。
@router.post("/api/simulation-runs/{run_id}/device-tasks/dispatch")
def dispatch_device_tasks(run_id: str, payload: DeviceTaskDispatchRequest, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return SimulationService(db, runtime_store).dispatch_device_tasks(run_id, payload)


# 清空运行时状态：DELETE /api/simulation-runs/{run_id}/runtime-state，删除指定仿真运行的临时状态。
@router.delete("/api/simulation-runs/{run_id}/runtime-state")
def clear_runtime_state(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return SimulationService(db, runtime_store).clear_runtime_state(run_id)
