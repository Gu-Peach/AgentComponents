from __future__ import annotations

from typing import Any

from app.agent.contracts import AGENT_EVENT_TYPES
from app.db import models
from app.repositories.sql import AgentRepository
from app.services.ids import new_id


class AgentEventEmitter:
    """Persist ordered Agent events so a run can be replayed from the database."""

    def __init__(self, repo: AgentRepository) -> None:
        self.repo = repo

    def emit(self, agent_run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> models.AgentEvent:
        if event_type not in AGENT_EVENT_TYPES:
            raise ValueError(f"Unsupported agent event type: {event_type}")
        event = models.AgentEvent(
            id=new_id("agevt"),
            agent_run_id=agent_run_id,
            sequence=self.repo.next_event_sequence(agent_run_id),
            event_type=event_type,
            payload=payload or {},
        )
        self.repo.add_event(event)
        self.repo.db.flush()
        return event
