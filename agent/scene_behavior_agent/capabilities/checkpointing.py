"""Optional LangGraph checkpointer integration."""

from __future__ import annotations

from typing import Any


def build_checkpointer(kind: str = "memory") -> Any | None:
    """Build an optional LangGraph checkpointer.

    Returns None when langgraph is unavailable. Production can replace this with
    a Postgres/Redis-backed checkpointer while keeping graph construction stable.
    """

    if kind != "memory":
        raise ValueError(f"Unsupported checkpointer kind: {kind}")
    try:
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        return None
    return MemorySaver()
