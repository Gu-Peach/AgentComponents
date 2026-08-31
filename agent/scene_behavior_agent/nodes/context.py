"""Context-building LangGraph nodes."""

from __future__ import annotations

from ..models.llm import PlannerModel
from ..schemas.config import AgentConfig
from ..schemas.state import AgentState
from ..tools.device_spec_reader import DeviceSpecReader
from ..tools.connection_validator import ConnectionValidator
from ..tools.scene_reader import SceneReader


def load_scene_node(config: AgentConfig):
    reader = SceneReader()

    def node(state: AgentState) -> AgentState:
        scene_facts = reader.read(state["scene_document_ref"])
        return {
            **state,
            "scene_id": scene_facts.get("scene_id", state.get("scene_id", "unknown_scene")),
            "scene_revision": str(scene_facts.get("scene_revision", state.get("scene_revision", "unknown_revision"))),
            "scene_facts": scene_facts,
            "device_spec_refs": scene_facts.get("device_spec_refs", []),
        }

    return node


def load_device_specs_node(config: AgentConfig):
    reader = DeviceSpecReader(config)

    def node(state: AgentState) -> AgentState:
        capabilities = reader.read_many(state.get("device_spec_refs", []))
        return {**state, "device_capabilities": capabilities}

    return node


def intent_parser_node(model: PlannerModel):
    def node(state: AgentState) -> AgentState:
        return {**state, "intent": model.parse_intent(state.get("user_goal_raw", ""))}

    return node


def connection_validation_node():
    validator = ConnectionValidator()

    def node(state: AgentState) -> AgentState:
        report = validator.validate(state.get("scene_facts", {}), state.get("device_capabilities", {}))
        return {**state, "connection_validation": report}

    return node
