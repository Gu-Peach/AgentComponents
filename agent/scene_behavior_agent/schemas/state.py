"""Shared LangGraph AgentState definitions.

The fields mirror docs/design/agent_design.md.  TypedDict keeps the package
lightweight and compatible with LangGraph's state graph API without requiring
pydantic at import time.
"""

from __future__ import annotations

from typing import Any, Literal, NotRequired, TypedDict

ApprovalStatus = Literal["pending", "approved", "rejected", "needs_revision"]


class ValidationIssue(TypedDict):
    severity: Literal["error", "warning"]
    code: str
    message: str
    path: NotRequired[str]


class ValidationReport(TypedDict):
    valid: bool
    issues: list[ValidationIssue]


class AgentState(TypedDict, total=False):
    run_id: str
    scene_id: str
    scene_revision: str
    user_goal_raw: str
    intent: dict[str, Any]
    scene_document_ref: str
    scene_facts: dict[str, Any]
    device_spec_refs: list[str]
    device_capabilities: dict[str, Any]
    connection_validation: ValidationReport
    process_modules: list[dict[str, Any]]
    event_bus_draft: dict[str, Any]
    state_model_draft: dict[str, Any]
    behavior_rules_draft: list[dict[str, Any]]
    state_transition_rules_draft: list[dict[str, Any]]
    policies_draft: dict[str, Any]
    completion_conditions_draft: list[Any]
    failure_observations_draft: list[dict[str, Any]]
    scene_behavior_graph_draft: dict[str, Any]
    validation_report: ValidationReport
    repair_attempts: int
    explanation: str
    approval_status: ApprovalStatus
    final_scene_behavior_graph: dict[str, Any]
    messages: list[dict[str, Any]]
    output_path: str
