from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.serializers import agent_artifact_response, agent_event_response, agent_run_response
from app.agent.contracts import AGENT_EVENT_TYPES, ARTIFACT_TYPES, SchemaContractRegistry
from app.agent.graph import AgentGraphDefinition
from app.db.session import get_db
from app.dependencies import get_runtime_store
from app.schemas.domain import AgentArtifactResponse, AgentEventResponse, AgentRunCreate, AgentRunResponse, PatchApplyRequest, PatchApplyResponse
from app.services.agent_service import AgentService
from app.services.runtime_state import RuntimeStateStore

router = APIRouter(tags=["agent"])


@router.get("/api/agent/contracts")
def get_agent_contracts() -> dict:
    return {
        "schemas": SchemaContractRegistry().list_contracts(),
        "artifact_types": sorted(ARTIFACT_TYPES),
        "event_types": sorted(AGENT_EVENT_TYPES),
    }


@router.get("/api/agent/graph")
def get_agent_graph() -> dict:
    return AgentGraphDefinition().as_dict()


@router.post("/api/projects/{project_id}/agent-runs", response_model=AgentRunResponse)
def create_agent_run(project_id: str, payload: AgentRunCreate, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return agent_run_response(AgentService(db, runtime_store).create_run(project_id, payload))


@router.get("/api/agent-runs/{agent_run_id}", response_model=AgentRunResponse)
def get_agent_run(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return agent_run_response(AgentService(db, runtime_store).get_run(agent_run_id))


@router.post("/api/agent-runs/{agent_run_id}/cancel", response_model=AgentRunResponse)
def cancel_agent_run(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return agent_run_response(AgentService(db, runtime_store).cancel_run(agent_run_id))


@router.post("/api/agent-runs/{agent_run_id}/resume", response_model=AgentRunResponse)
def resume_agent_run(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return agent_run_response(AgentService(db, runtime_store).resume_run(agent_run_id))


@router.get("/api/agent-runs/{agent_run_id}/artifacts", response_model=list[AgentArtifactResponse])
def list_agent_artifacts(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> list[dict]:
    return [agent_artifact_response(artifact) for artifact in AgentService(db, runtime_store).list_artifacts(agent_run_id)]


@router.get("/api/agent-runs/{agent_run_id}/events", response_model=list[AgentEventResponse])
def list_agent_events(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> list[dict]:
    return [agent_event_response(event) for event in AgentService(db, runtime_store).list_events(agent_run_id)]


@router.get("/api/agent-runs/{agent_run_id}/events/stream")
def stream_agent_events(agent_run_id: str, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> StreamingResponse:
    service = AgentService(db, runtime_store)
    events = [agent_event_response(event) for event in service.list_events(agent_run_id)]

    def event_iter():
        for event in events:
            yield f"event: {event['event_type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_iter(), media_type="text/event-stream")


@router.post("/api/agent-runs/{agent_run_id}/artifacts/{artifact_id}/apply", response_model=PatchApplyResponse)
def apply_agent_artifact(agent_run_id: str, artifact_id: str, payload: PatchApplyRequest, db: Session = Depends(get_db), runtime_store: RuntimeStateStore = Depends(get_runtime_store)) -> dict:
    return AgentService(db, runtime_store).apply_artifact(agent_run_id, artifact_id, payload.expected_base_revision, approved_by_user=payload.approved_by_user)
