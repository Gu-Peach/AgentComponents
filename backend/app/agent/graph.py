from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentGraphNode:
    name: str
    responsibility: str


class AgentGraphDefinition:
    """LangGraph-shaped execution plan used by AgentService.

    The backend keeps the node contract explicit without taking a runtime
    dependency on LangGraph yet. Each node has a deterministic service/tool
    implementation, and later can be swapped into real LangGraph nodes.
    """

    nodes = [
        AgentGraphNode("LoadContextNode", "Read SceneDocument and lock base revision."),
        AgentGraphNode("LoadDeviceCapabilitiesNode", "Read DeviceSpec documents and build capability index."),
        AgentGraphNode("BuildOrLoadTopologyNode", "Load matching topology or rebuild deterministic graph."),
        AgentGraphNode("ClassifyIntentNode", "Parse user intent into a structured task route."),
        AgentGraphNode("ResolveSlotsNode", "Resolve scene instance, port, signal, and target-slot mentions."),
        AgentGraphNode("RouteTaskNode", "Select query, topology, parameter, behavior, runtime, or scenario subgraph."),
        AgentGraphNode("ValidateArtifactNode", "Run schema and Guardian validation for every candidate artifact."),
        AgentGraphNode("RepairOrInterruptNode", "Limit repairs and produce questions for unresolved low-confidence facts."),
        AgentGraphNode("ExplainNode", "Summarize what was inferred, validated, or left for review."),
        AgentGraphNode("StageOrApplyNode", "Persist candidate artifacts and optionally apply safe patches."),
        AgentGraphNode("EmitResultNode", "Finalize run response and replayable event trace."),
    ]

    def node_names(self) -> list[str]:
        return [node.name for node in self.nodes]

    def as_dict(self) -> dict:
        return {"graph_type": "agent_execution_graph", "nodes": [node.__dict__ for node in self.nodes]}
