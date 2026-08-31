"""Executable runners for the SceneBehaviorGraph Agent."""

from __future__ import annotations

from uuid import uuid4

from ..models.llm import DeterministicPlanner, PlannerModel
from ..nodes.context import connection_validation_node, intent_parser_node, load_device_specs_node, load_scene_node
from ..nodes.modeling import (
    behavior_rule_node,
    device_capability_summarizer_node,
    event_state_modeler_node,
    policy_synthesizer_node,
    process_decomposer_node,
    scene_understanding_node,
)
from ..nodes.routers import route_connection_validation, route_graph_validation, route_human_review
from ..nodes.validation import (
    assemble_graph_node,
    explanation_node,
    finalize_graph_node,
    graph_validation_node,
    human_review_node,
    repair_graph_node,
)
from ..schemas.config import AgentConfig, default_config
from ..schemas.state import AgentState


class SequentialSceneBehaviorAgent:
    """Fallback runner with the same node ordering as the LangGraph graph."""

    def __init__(self, config: AgentConfig | None = None, model: PlannerModel | None = None):
        self.config = config or default_config()
        self.model = model or DeterministicPlanner()

    def invoke(self, initial_state: AgentState) -> AgentState:
        state: AgentState = {"run_id": f"agent_run_{uuid4().hex}", "repair_attempts": 0, **initial_state}
        for node in [
            load_scene_node(self.config),
            load_device_specs_node(self.config),
            intent_parser_node(self.model),
            connection_validation_node(),
        ]:
            state = node(state)
        if route_connection_validation(state) == "invalid":
            state = explanation_node(self.model)(state)
            state = human_review_node(self.config)(state)
            return state

        for node in [
            scene_understanding_node(self.model),
            device_capability_summarizer_node(self.model),
            process_decomposer_node(self.model),
            event_state_modeler_node(self.model),
            behavior_rule_node(self.model),
            policy_synthesizer_node(self.model),
            assemble_graph_node(),
            graph_validation_node(),
        ]:
            state = node(state)

        while route_graph_validation(state, self.config.max_repair_attempts) == "repair":
            state = repair_graph_node(self.model)(state)
            state = assemble_graph_node()(state)
            state = graph_validation_node()(state)

        state = explanation_node(self.model)(state)
        state = human_review_node(self.config)(state)
        if route_human_review(state) == "approved":
            state = finalize_graph_node(self.config)(state)
        return state


def invoke_agent(initial_state: AgentState, config: AgentConfig | None = None, model: PlannerModel | None = None) -> AgentState:
    """Invoke a real LangGraph app if available, otherwise use fallback runner."""

    config = config or default_config()
    model = model or DeterministicPlanner()
    try:
        from .builder import build_graph

        app = build_graph(config=config, model=model)
        return app.invoke({"run_id": f"agent_run_{uuid4().hex}", "repair_attempts": 0, **initial_state})
    except ImportError:
        return SequentialSceneBehaviorAgent(config=config, model=model).invoke(initial_state)
