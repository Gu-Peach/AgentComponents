from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.serializers import simulation_run_response
from app.db.session import get_db
from app.dependencies import get_runtime_store
from app.schemas.domain import RuntimeSnapshotPut, SignalEmitRequest, SimulationRunCreate, SimulationRunResponse
from app.services.runtime_state import RuntimeStateStore
from app.services.simulation_service import SimulationService

router = APIRouter(tags=["simulation"])


@router.post("/api/projects/{project_id}/simulation-runs", response_model=SimulationRunResponse)
def create_simulation_run(project_id: str, payload: SimulationRunCreate, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return simulation_run_response(SimulationService(db, runtime_store).create_run(project_id, payload))


@router.get("/api/simulation-runs/{run_id}", response_model=SimulationRunResponse)
def get_simulation_run(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return simulation_run_response(SimulationService(db, runtime_store).get_run(run_id))


@router.get("/api/simulation-runs/{run_id}/runtime-snapshot")
def get_runtime_snapshot(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    snapshot = SimulationService(db, runtime_store).get_snapshot(run_id)
    return {"run_id": run_id, "snapshot": snapshot}


@router.put("/api/simulation-runs/{run_id}/runtime-snapshot")
def put_runtime_snapshot(run_id: str, payload: RuntimeSnapshotPut, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    snapshot = SimulationService(db, runtime_store).put_snapshot(run_id, payload)
    return {"run_id": run_id, "snapshot": snapshot}


@router.post("/api/simulation-runs/{run_id}/signals/{signal_id}/emit")
def emit_signal(run_id: str, signal_id: str, payload: SignalEmitRequest, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return SimulationService(db, runtime_store).emit_signal(run_id, signal_id, payload)


@router.delete("/api/simulation-runs/{run_id}/runtime-state")
def clear_runtime_state(run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return SimulationService(db, runtime_store).clear_runtime_state(run_id)

