"""Validation, review and finalization nodes."""

from __future__ import annotations

from pathlib import Path

from ..models.llm import PlannerModel
from ..schemas.config import AgentConfig
from ..schemas.state import AgentState
from ..tools.graph_validator import GraphValidator
from ..tools.explanation_renderer import ExplanationRenderer
from ..tools.writer import SceneBehaviorGraphWriter


def assemble_graph_node():
    writer = SceneBehaviorGraphWriter()

    def node(state: AgentState) -> AgentState:
        return {**state, "scene_behavior_graph_draft": writer.assemble(state)}

    return node


def graph_validation_node():
    validator = GraphValidator()

    def node(state: AgentState) -> AgentState:
        report = validator.validate(
            state.get("scene_behavior_graph_draft", {}),
            state.get("scene_facts", {}),
            state.get("device_capabilities", {}),
        )
        return {**state, "validation_report": report}

    return node


def repair_graph_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        repaired = model.repair(dict(state))
        return repaired

    return node


def explanation_node(model: PlannerModel):
    renderer = ExplanationRenderer()

    def node(state: AgentState) -> AgentState:
        if state.get("scene_behavior_graph_draft"):
            return {**state, "explanation": renderer.render(state)}
        return {**state, "explanation": model.explain(state)}

    return node


def human_review_node(config: AgentConfig):
    def node(state: AgentState) -> AgentState:
        if config.auto_approve:
            return {**state, "approval_status": "approved"}
        return {**state, "approval_status": "pending"}

    return node


def finalize_graph_node(config: AgentConfig):
    writer = SceneBehaviorGraphWriter()

    def node(state: AgentState) -> AgentState:
        graph = state.get("scene_behavior_graph_draft", {})
        output_path = state.get("output_path")
        if not output_path:
            output_path = str(config.default_output_dir / "scene_behavior_graph.generated.json")
        writer.write(Path(output_path), graph)
        return {**state, "final_scene_behavior_graph": graph, "output_path": output_path}

    return node
