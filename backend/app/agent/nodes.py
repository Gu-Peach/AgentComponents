from __future__ import annotations

from typing import Any

from app.agent.compiler import BehaviorGraphBuilder, IntentParser, ParameterBinder, ParameterExtractor, ProcessEdgePlanner, SignalRoutePlanner, SlotResolver, behavior_graph_artifact, parameter_binding_artifact, topology_completion_artifacts
from app.agent.contracts import AgentArtifactContract, AgentState
from app.agent.diagnostics import runtime_diagnostic_artifact
from app.agent.scenarios import scenario_experiment_artifact


class LoadContextNode:
    def run(self, state: AgentState, scene_doc: dict[str, Any]) -> AgentState:
        state.scene = scene_doc
        state.scene_id = scene_doc.get("scene_id", state.scene_id)
        state.base_scene_revision = int(scene_doc.get("revision", state.base_scene_revision))
        return state


class LoadDeviceCapabilitiesNode:
    def run(self, state: AgentState, specs: dict[str, dict[str, Any]]) -> AgentState:
        state.device_specs = specs
        return state


class BuildOrLoadTopologyNode:
    def run(self, state: AgentState, topology: dict[str, Any]) -> AgentState:
        state.topology = topology
        return state


class ClassifyIntentNode:
    def run(self, state: AgentState, simulation_run_id: str | None = None, document_text: str | None = None) -> AgentState:
        state.intent = IntentParser().parse(state.user_message, simulation_run_id=simulation_run_id, document_text=document_text)
        return state


class ResolveSlotsNode:
    def run(self, state: AgentState) -> AgentState:
        state.resolved_slots = SlotResolver().resolve(state.scene or {}, state.topology, state.user_message)
        return state


class ProcessCompileSubgraph:
    def run(self, state: AgentState, physical_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return ProcessEdgePlanner().plan_from_physical(state.scene or {}, state.device_specs, physical_edges)


class SignalCompileSubgraph:
    def run(self, state: AgentState, process_edges: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        return SignalRoutePlanner().plan(state.scene or {}, state.device_specs, process_edges)


class BehaviorGraphCompileSubgraph:
    def run(self, state: AgentState) -> AgentArtifactContract:
        return behavior_graph_artifact(state.scene or {}, state.device_specs, state.topology, state.user_message)


class ParameterFillSubgraph:
    def run(self, state: AgentState, text: str) -> AgentArtifactContract | None:
        return parameter_binding_artifact(state.scene or {}, state.device_specs, text)


class TopologyDiagnosisSubgraph:
    def run(self, state: AgentState) -> list[AgentArtifactContract]:
        return topology_completion_artifacts(state.scene or {}, state.device_specs)


class RuntimeDiagnosisSubgraph:
    def run(self, state: AgentState, snapshot: dict[str, Any] | None, event_log: list[dict[str, Any]]) -> tuple[AgentArtifactContract, list[AgentArtifactContract]]:
        return runtime_diagnostic_artifact(state.scene or {}, state.device_specs, snapshot, event_log)


class ScenarioCompareSubgraph:
    def run(self, state: AgentState, scenario_count: int = 2) -> AgentArtifactContract:
        return scenario_experiment_artifact(state.scene or {}, scenario_count)


class RouteTaskNode:
    def route(self, state: AgentState) -> str:
        return state.intent.get("intent_type", "query_scene")


class ValidateArtifactNode:
    def run(self, artifact: AgentArtifactContract) -> AgentArtifactContract:
        return artifact


class RepairOrInterruptNode:
    max_repair_attempts = 2

    def should_interrupt(self, state: AgentState) -> bool:
        return state.repair_attempts >= self.max_repair_attempts


class ExplainNode:
    def run(self, state: AgentState) -> dict[str, Any]:
        return {
            "intent": state.intent,
            "resolved_slots": state.resolved_slots,
            "artifacts": [artifact.artifact_type for artifact in state.candidate_artifacts],
        }


class StageOrApplyNode:
    def run(self, state: AgentState) -> dict[str, Any]:
        return {"candidate_artifacts": len(state.candidate_artifacts), "base_scene_revision": state.base_scene_revision}


class EmitResultNode:
    def run(self, state: AgentState) -> dict[str, Any]:
        return state.final_response or {"message": "Agent run reached EmitResultNode."}


class SceneQuerySubgraph:
    def run(self, state: AgentState) -> dict[str, Any]:
        return {
            "scene_id": state.scene_id,
            "revision": state.base_scene_revision,
            "instance_count": len((state.scene or {}).get("instances", [])),
            "edge_counts": {section: len((state.scene or {}).get(section, [])) for section in ["physical_edges", "process_edges", "signal_edges"]},
        }


class SignalPortResolver:
    def resolve(self, state: AgentState, instance_id: str, semantic: str) -> list[str]:
        instance = next((item for item in (state.scene or {}).get("instances", []) if item.get("instance_id") == instance_id), None)
        spec = state.device_specs.get(instance.get("spec_id")) if instance else None
        if not spec:
            return []
        semantic_lower = semantic.lower()
        return [signal["port_id"] for signal in spec.get("signal_ports", []) if semantic_lower in signal.get("port_id", "").lower() or semantic_lower in signal.get("semantic", "").lower()]
