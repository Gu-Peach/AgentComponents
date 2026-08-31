"""Conditional edge helpers for LangGraph."""

from __future__ import annotations

from ..schemas.state import AgentState


def route_connection_validation(state: AgentState) -> str:
    report = state.get("connection_validation", {"valid": False})
    return "valid" if report.get("valid") else "invalid"


def route_graph_validation(state: AgentState, max_repair_attempts: int = 2) -> str:
    report = state.get("validation_report", {"valid": False})
    if report.get("valid"):
        return "valid"
    if int(state.get("repair_attempts", 0)) < max_repair_attempts:
        return "repair"
    return "failed"


def route_human_review(state: AgentState) -> str:
    status = state.get("approval_status", "pending")
    if status == "approved":
        return "approved"
    if status == "needs_revision":
        return "revise"
    return "rejected"
