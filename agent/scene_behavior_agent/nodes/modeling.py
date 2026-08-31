"""Behavior modeling LangGraph nodes."""

from __future__ import annotations

from ..models.llm import PlannerModel
from ..schemas.state import AgentState
from ..tools.policy_library import PolicyLibrary


def scene_understanding_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        scene_facts = dict(state.get("scene_facts", {}))
        scene_facts["summary"] = model.summarize_scene(scene_facts, state.get("intent", {}))
        return {**state, "scene_facts": scene_facts}

    return node


def device_capability_summarizer_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        capabilities = dict(state.get("device_capabilities", {}))
        capabilities["summary_text"] = model.summarize_capabilities(capabilities)
        return {**state, "device_capabilities": capabilities}

    return node


def process_decomposer_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        return {**state, "process_modules": model.decompose_process(state)}

    return node


def event_state_modeler_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        event_bus, state_model = model.model_event_state(state)
        return {**state, "event_bus_draft": event_bus, "state_model_draft": state_model}

    return node


def behavior_rule_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        rules, transitions, completion = model.model_behavior_rules(state)
        return {
            **state,
            "behavior_rules_draft": rules,
            "state_transition_rules_draft": transitions,
            "completion_conditions_draft": completion,
        }

    return node


def policy_synthesizer_node(model: PlannerModel):
    library = PolicyLibrary()

    def node(state: AgentState) -> AgentState:
        policies = library.infer_policies(state.get("scene_facts", {}), state.get("process_modules", []))
        policies.setdefault(
            "target_conveyor_selection",
            {"type": "load_balancing", "candidates": "output_conveyors", "prefer": "lowest_current_load_not_blocked"},
        )
        failure_observations = [
            {"observation_id": "deadlock_detected", "condition": "no_enabled_behavior and completion_conditions_not_met"},
            {"observation_id": "resource_conflict", "condition": "resource lock conflict exceeds retry threshold"},
        ]
        return {**state, "policies_draft": policies, "failure_observations_draft": failure_observations}

    return node
