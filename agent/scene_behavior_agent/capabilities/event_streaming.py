"""Lightweight event streaming primitives for agent observability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class AgentEvent:
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class EventRecorder:
    """In-process event recorder used by local runs and tests."""

    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    def emit(self, event_type: str, **payload: Any) -> None:
        self.events.append(AgentEvent(event_type=event_type, payload=payload))

    def as_dicts(self) -> list[dict[str, Any]]:
        return [
            {"event_type": event.event_type, "payload": event.payload, "created_at": event.created_at}
            for event in self.events
        ]
