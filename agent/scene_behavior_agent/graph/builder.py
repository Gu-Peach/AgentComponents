"""LangGraph builder for SceneBehaviorGraph Agent.

The code builds a real StateGraph when langgraph is installed.  For local docs
and schema development, use SequentialSceneBehaviorAgent from runner.py.
"""

from __future__ import annotations

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


def build_graph(config: AgentConfig | None = None, model: PlannerModel | None = None):
    """Build a LangGraph StateGraph.

    Raises ImportError if langgraph is not installed; callers can fallback to
    SequentialSceneBehaviorAgent.
    """

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - depends on optional package
        raise ImportError("langgraph is not installed; use SequentialSceneBehaviorAgent for local fallback") from exc

    config = config or default_config()
    model = model or DeterministicPlanner()
    graph = StateGraph(AgentState)

    graph.add_node("load_scene", load_scene_node(config))
    graph.add_node("load_device_specs", load_device_specs_node(config))
    graph.add_node("parse_intent", intent_parser_node(model))
    graph.add_node("validate_connections", connection_validation_node())
    graph.add_node("understand_scene", scene_understanding_node(model))
    graph.add_node("summarize_capabilities", device_capability_summarizer_node(model))
    graph.add_node("decompose_process", process_decomposer_node(model))
    graph.add_node("model_event_state", event_state_modeler_node(model))
    graph.add_node("model_behavior_rules", behavior_rule_node(model))
    graph.add_node("synthesize_policies", policy_synthesizer_node(model))
    graph.add_node("assemble_graph", assemble_graph_node())
    graph.add_node("validate_graph", graph_validation_node())
    graph.add_node("repair_graph", repair_graph_node(model))
    graph.add_node("explain", explanation_node(model))
    graph.add_node("human_review", human_review_node(config))
    graph.add_node("finalize", finalize_graph_node(config))

    graph.add_edge(START, "load_scene")
    graph.add_edge("load_scene", "load_device_specs")
    graph.add_edge("load_device_specs", "parse_intent")
    graph.add_edge("parse_intent", "validate_connections")
    graph.add_conditional_edges(
        "validate_connections",
        route_connection_validation,
        {"valid": "understand_scene", "invalid": "explain"},
    )
    graph.add_edge("understand_scene", "summarize_capabilities")
    graph.add_edge("summarize_capabilities", "decompose_process")
    graph.add_edge("decompose_process", "model_event_state")
    graph.add_edge("model_event_state", "model_behavior_rules")
    graph.add_edge("model_behavior_rules", "synthesize_policies")
    graph.add_edge("synthesize_policies", "assemble_graph")
    graph.add_edge("assemble_graph", "validate_graph")
    graph.add_conditional_edges(
        "validate_graph",
        lambda state: route_graph_validation(state, config.max_repair_attempts),
        {"valid": "explain", "repair": "repair_graph", "failed": "explain"},
    )
    graph.add_edge("repair_graph", "assemble_graph")
    graph.add_edge("explain", "human_review")
    graph.add_conditional_edges(
        "human_review",
        route_human_review,
        {"approved": "finalize", "revise": "decompose_process", "rejected": END},
    )
    graph.add_edge("finalize", END)
    return graph.compile()
