from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

from app.agent.contracts import AgentArtifactContract, PatchEnvelope, ValidationReport
from app.services.ids import new_id
from app.services.interface_compiler import InterfaceCompiler
from app.services.scene_behavior_graph_validator import validate_scene_behavior_graph_for_runtime
from app.services.topology_builder import TopologyBuilder
from app.services.validation import build_scene_context, validate_physical_edge, validate_process_edge, validate_signal_edge


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_")


def _parse_endpoint(endpoint: str) -> tuple[str, str]:
    instance_id, port_id = endpoint.split(".", 1)
    return instance_id, port_id


class CapabilityIndexer:
    def build(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        instances: dict[str, dict[str, Any]] = {}
        for instance in scene_doc.get("instances", []):
            spec = specs.get(instance.get("spec_id"), {})
            instance_id = instance.get("instance_id")
            params = {
                key: value.get("default")
                for key, value in spec.get("params_schema", {}).items()
                if isinstance(value, dict) and "default" in value
            }
            params.update(instance.get("param_overrides", {}))
            instances[instance_id] = {
                "instance_id": instance_id,
                "spec_id": instance.get("spec_id"),
                "device_type": instance.get("device_type") or spec.get("device_type"),
                "params": params,
                "physical_interfaces": deepcopy(spec.get("physical_interfaces", [])),
                "process_ports": deepcopy(spec.get("process_ports", [])),
                "signal_ports": deepcopy(spec.get("signal_ports", [])),
                "transport_behaviors": deepcopy(spec.get("transport_behaviors", [])),
                "resources": deepcopy(spec.get("runtime_contract", {}).get("resources", [])),
                "capacity": deepcopy(spec.get("runtime_contract", {}).get("capacity", {})),
            }
        return {
            "schema_type": "CapabilityIndex",
            "scene_id": scene_doc.get("scene_id"),
            "scene_revision": scene_doc.get("revision", 0),
            "instances": instances,
            "counts": {
                "instances": len(instances),
                "physical_interfaces": sum(len(item["physical_interfaces"]) for item in instances.values()),
                "process_ports": sum(len(item["process_ports"]) for item in instances.values()),
                "signal_ports": sum(len(item["signal_ports"]) for item in instances.values()),
                "transport_behaviors": sum(len(item["transport_behaviors"]) for item in instances.values()),
            },
        }


class WorldFrameResolver:
    def resolve_interface(self, instance: dict[str, Any], interface: dict[str, Any]) -> dict[str, Any]:
        transform = instance.get("transform", {})
        base_position = transform.get("position", [0, 0, 0])
        rotation = transform.get("rotation_euler", [0, 0, 0])
        frame = interface.get("local_frame", {})
        local_position = frame.get("position") or interface.get("local_position") or [0, 0, 0]
        local_forward = frame.get("forward") or interface.get("local_forward") or [1, 0, 0]
        yaw = rotation[2] if len(rotation) > 2 else 0
        position = self._add(base_position, self._rotate_z(local_position, yaw))
        forward = self._normalize(self._rotate_z(local_forward, yaw))
        return {
            "instance_id": instance.get("instance_id"),
            "interface_id": interface.get("interface_id"),
            "endpoint": f"{instance.get('instance_id')}.{interface.get('interface_id')}",
            "kind": interface.get("kind"),
            "direction": interface.get("direction"),
            "material_classes": interface.get("material_classes", []),
            "position": position,
            "forward": forward,
        }

    @staticmethod
    def _rotate_z(vector: list[float], yaw: float) -> list[float]:
        x, y, z = vector[:3]
        return [x * math.cos(yaw) - y * math.sin(yaw), x * math.sin(yaw) + y * math.cos(yaw), z]

    @staticmethod
    def _add(a: list[float], b: list[float]) -> list[float]:
        return [float(a[i]) + float(b[i]) for i in range(3)]

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        length = math.sqrt(sum(float(value) * float(value) for value in vector[:3])) or 1.0
        return [float(value) / length for value in vector[:3]]


class EdgeConfidenceScorer:
    def score(self, source: dict[str, Any], target: dict[str, Any], distance_m: float, max_distance_m: float) -> float:
        distance_score = max(0.0, 1.0 - distance_m / max_distance_m)
        direction_score = 0.5 + 0.5 * max(0.0, self._dot(source.get("forward", []), target.get("forward", [])) * -1)
        material_score = 1.0 if self._materials_compatible(source, target) else 0.0
        kind_score = 1.0 if source.get("kind") == target.get("kind") else 0.65
        return round(0.45 * distance_score + 0.2 * direction_score + 0.25 * material_score + 0.1 * kind_score, 3)

    @staticmethod
    def _dot(a: list[float], b: list[float]) -> float:
        if len(a) < 3 or len(b) < 3:
            return 0.0
        return sum(float(a[i]) * float(b[i]) for i in range(3))

    @staticmethod
    def _materials_compatible(source: dict[str, Any], target: dict[str, Any]) -> bool:
        source_classes = set(source.get("material_classes") or [])
        target_classes = set(target.get("material_classes") or [])
        return not source_classes or not target_classes or not source_classes.isdisjoint(target_classes)


class ImplicitEdgeCandidateGenerator:
    def __init__(self, max_distance_m: float = 2.0, min_confidence: float = 0.35) -> None:
        self.max_distance_m = max_distance_m
        self.min_confidence = min_confidence
        self.frame_resolver = WorldFrameResolver()
        self.scorer = EdgeConfidenceScorer()

    def generate(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        endpoints = self._endpoints(scene_doc, specs)
        existing = {(edge.get("source"), edge.get("target")) for edge in scene_doc.get("physical_edges", [])}
        candidates: list[dict[str, Any]] = []
        for source in endpoints:
            if source.get("direction") not in {"output", "bidirectional"}:
                continue
            for target in endpoints:
                if source.get("instance_id") == target.get("instance_id"):
                    continue
                if target.get("direction") not in {"input", "bidirectional"}:
                    continue
                if (source["endpoint"], target["endpoint"]) in existing:
                    continue
                if not EdgeConfidenceScorer._materials_compatible(source, target):
                    continue
                distance_m = self._distance(source["position"], target["position"])
                if distance_m > self.max_distance_m:
                    continue
                confidence = self.scorer.score(source, target, distance_m, self.max_distance_m)
                if confidence < self.min_confidence:
                    continue
                candidates.append(
                    {
                        "edge_id": f"phys_agent_{_safe_id(source['endpoint'])}_to_{_safe_id(target['endpoint'])}",
                        "source": source["endpoint"],
                        "target": target["endpoint"],
                        "edge_type": "physical_connection",
                        "connection_method": "agent_implicit_geometry",
                        "compiled_from": None,
                        "is_inferred": True,
                        "confidence": confidence,
                        "compatibility_result": {"status": "compatible", "matched_fields": ["material_class"], "missing_fields": []},
                        "snap_result": {"distance_m": round(distance_m, 4), "angle_deg": None, "within_tolerance": distance_m <= 0.25, "retain_offset": distance_m > 0.25},
                    }
                )
        return sorted(candidates, key=lambda item: (-item["confidence"], item["source"], item["target"]))

    def _endpoints(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        endpoints: list[dict[str, Any]] = []
        for instance in scene_doc.get("instances", []):
            spec = specs.get(instance.get("spec_id"), {})
            for interface in spec.get("physical_interfaces", []):
                if interface.get("kind") != "material":
                    continue
                endpoints.append(self.frame_resolver.resolve_interface(instance, interface))
        return endpoints

    @staticmethod
    def _distance(a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((float(a[i]) - float(b[i])) ** 2 for i in range(3)))


class ProcessEdgePlanner:
    def plan_from_physical(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], physical_edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
        existing = {(edge.get("source"), edge.get("target")) for edge in scene_doc.get("process_edges", [])}
        planned: list[dict[str, Any]] = []
        for edge in physical_edges:
            source_process = self._process_port_for_physical(edge["source"], scene_doc, specs)
            target_process = self._process_port_for_physical(edge["target"], scene_doc, specs)
            if not source_process or not target_process or (source_process, target_process) in existing:
                continue
            planned.append(
                {
                    "edge_id": f"proc_agent_{_safe_id(source_process)}_to_{_safe_id(target_process)}",
                    "source": source_process,
                    "target": target_process,
                    "edge_type": "material_flow",
                    "material_classes": edge.get("compatibility_result", {}).get("material_classes", ["workpiece", "workpiece_carrier"]),
                    "priority": 100,
                    "conditions": [],
                    "compiled_physical_edges": [edge["edge_id"]],
                    "compiled_signal_edges": [],
                    "is_inferred": True,
                    "confidence": edge.get("confidence", 0.0),
                }
            )
        return planned

    @staticmethod
    def _process_port_for_physical(endpoint: str, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> str | None:
        instance_id, interface_id = _parse_endpoint(endpoint)
        instance = next((item for item in scene_doc.get("instances", []) if item.get("instance_id") == instance_id), None)
        spec = specs.get(instance.get("spec_id")) if instance else None
        if not spec:
            return None
        for binding in spec.get("interface_bindings", []):
            if binding.get("physical_interface") == interface_id and binding.get("process_port"):
                return f"{instance_id}.{binding['process_port']}"
        for port in spec.get("process_ports", []):
            if port.get("bound_physical_interface") == interface_id:
                return f"{instance_id}.{port['port_id']}"
        return None


class SignalRoutePlanner:
    def plan(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], process_edges: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        draft = deepcopy(scene_doc)
        if process_edges:
            existing = {(edge.get("source"), edge.get("target")) for edge in draft.get("process_edges", [])}
            for edge in process_edges:
                if (edge.get("source"), edge.get("target")) not in existing:
                    draft.setdefault("process_edges", []).append(edge)
        return InterfaceCompiler().compile(draft, specs).get("compiled_signal_edges", [])


class BehaviorGraphBuilder:
    def build(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], topology: dict[str, Any] | None, user_message: str = "") -> dict[str, Any]:
        capability_index = CapabilityIndexer().build(scene_doc, specs)
        signal_edges = [edge for edge in scene_doc.get("signal_edges", []) if edge.get("enabled", True)]
        if not signal_edges and scene_doc.get("process_edges"):
            signal_edges = SignalRoutePlanner().plan(scene_doc, specs)
        events: dict[str, dict[str, Any]] = {}
        routes: list[dict[str, Any]] = []
        rules: list[dict[str, Any]] = []
        modules = [
            {
                "module_id": instance.get("instance_id"),
                "module_type": instance.get("device_type"),
                "instance_id": instance.get("instance_id"),
                "capabilities_ref": instance.get("spec_id"),
            }
            for instance in scene_doc.get("instances", [])
        ]

        for edge in signal_edges:
            source = edge.get("source")
            target = edge.get("target")
            if not source or not target:
                continue
            events[source] = {"event_id": source, "source": source, "payload_schema": {"type": "object"}}
            events[target] = {"event_id": target, "source": target, "payload_schema": {"type": "object"}}
            target_instance, target_signal = _parse_endpoint(target)
            behavior_id = self._behavior_for_signal(scene_doc, specs, target_instance, target_signal)
            if not behavior_id:
                continue
            rule_id = f"rule_{_safe_id(source)}_to_{_safe_id(target)}"
            routes.append({"route_id": edge.get("route_id") or f"route_{rule_id}", "from": source, "to": {"type": "rule", "id": rule_id}})
            rules.append(
                {
                    "rule_id": rule_id,
                    "module_id": target_instance,
                    "trigger": {"type": "event", "event_id": source},
                    "guard": {"all": [f"device_states.{target_instance} != busy"]},
                    "policy": {"policy_id": "resource_lock", "inputs": {"instance_id": target_instance, "behavior_id": behavior_id}},
                    "action": {
                        "type": "start_behavior",
                        "instance_id": target_instance,
                        "behavior_id": behavior_id,
                        "payload": {"source_signal": source, "target_signal": target, "source_event": "source_event.payload"},
                    },
                }
            )

        graph = {
            "schema_id": f"scene_behavior_graph_{scene_doc.get('scene_id')}_agent_v0_1",
            "schema_type": "SceneBehaviorGraph",
            "version": "0.1.0",
            "goal": {"type": "user_intent", "text": user_message or "Run compiled scene behavior."},
            "source_topology_graph": (topology or {}).get("graph_id") or (topology or {}).get("topology_id"),
            "modules": modules,
            "event_bus": {"events": list(events.values()), "topics": [], "routes": routes, "subscriptions": {}},
            "state_model": {
                "device_states": {instance.get("instance_id"): "idle" for instance in scene_doc.get("instances", [])},
                "signal_values": {},
                "resource_locks": {},
                "active_actions": {},
                "capability_index_ref": capability_index.get("schema_type"),
            },
            "behavior_rules": rules,
            "state_transition_rules": [],
            "policies": self._policies(scene_doc, specs),
            "completion_conditions": [{"condition_id": "manual_or_event_completion", "type": "all_rules_idle_or_user_stop"}],
            "failure_observations": [
                {"observation_type": "timeout", "on_timeout": "raise_observation"},
                {"observation_type": "deadlock", "on_no_enabled_behavior": "raise_observation"},
                {"observation_type": "event_unconsumed", "on_unrouted_event": "raise_observation"},
            ],
        }
        if not rules:
            graph["event_bus"]["events"].append({"event_id": "agent.noop", "source": "agent", "payload_schema": {"type": "object"}})
            graph["behavior_rules"].append(
                {
                    "rule_id": "rule_agent_noop_diagnostic",
                    "module_id": "agent",
                    "trigger": {"type": "event", "event_id": "agent.noop"},
                    "guard": {"all": []},
                    "action": {"type": "emit_event", "event_id": "agent.noop.done", "payload": {}},
                }
            )
            graph["event_bus"]["events"].append({"event_id": "agent.noop.done", "source": "agent", "payload_schema": {"type": "object"}})
        return graph

    @staticmethod
    def _behavior_for_signal(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], instance_id: str, signal_id: str) -> str | None:
        instance = next((item for item in scene_doc.get("instances", []) if item.get("instance_id") == instance_id), None)
        spec = specs.get(instance.get("spec_id")) if instance else None
        if not spec:
            return None
        for behavior in spec.get("transport_behaviors", []):
            if signal_id in behavior.get("input_signals", []) or signal_id in behavior.get("control_signals", []):
                return behavior.get("behavior_id")
        for binding in spec.get("interface_bindings", []):
            if signal_id in binding.get("signal_ports", []) and binding.get("transport_behaviors"):
                return binding["transport_behaviors"][0]
        return None

    @staticmethod
    def _policies(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        policies: list[dict[str, Any]] = []
        for instance in scene_doc.get("instances", []):
            spec = specs.get(instance.get("spec_id"), {})
            for resource in spec.get("runtime_contract", {}).get("resources", []):
                policies.append(
                    {
                        "policy_id": f"resource_lock_{instance.get('instance_id')}_{resource.get('resource_id')}",
                        "type": "resource_lock",
                        "resource_id": f"{instance.get('instance_id')}.{resource.get('resource_id')}",
                        "exclusive": resource.get("exclusive", True),
                    }
                )
        return policies


class GuardianValidator:
    def validate_patch(self, artifact_type: str, envelope: PatchEnvelope, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> ValidationReport:
        draft = deepcopy(scene_doc)
        issues: list[dict[str, Any]] = []
        for op in envelope.operations:
            if op.op == "add" and op.path.endswith("/-"):
                section = op.path.strip("/").split("/", 1)[0]
                if section in {"physical_edges", "process_edges", "signal_edges"}:
                    draft.setdefault(section, []).append(op.value)
        ctx = build_scene_context(draft, specs)
        for edge in draft.get("physical_edges", []):
            issues.extend(self._map_issues(validate_physical_edge(ctx, edge.get("source", ""), edge.get("target", "")), f"physical_edges.{edge.get('edge_id')}"))
        for edge in draft.get("process_edges", []):
            issues.extend(self._map_issues(validate_process_edge(ctx, edge.get("source", ""), edge.get("target", "")), f"process_edges.{edge.get('edge_id')}"))
        for edge in draft.get("signal_edges", []):
            issues.extend(self._map_issues(validate_signal_edge(ctx, edge.get("source", ""), edge.get("target", ""), edge.get("transform")), f"signal_edges.{edge.get('edge_id')}"))
        return ValidationReport.from_issues(issues, {"artifact_type": artifact_type, "operation_count": len(envelope.operations)})

    def validate_behavior_graph(self, graph: dict[str, Any]) -> ValidationReport:
        result = validate_scene_behavior_graph_for_runtime(graph)
        return ValidationReport.from_issues(self._map_issues(result.get("issues", [])), result.get("summary", {}))

    @staticmethod
    def _map_issues(issues: list[dict[str, Any]], default_path: str | None = None) -> list[dict[str, Any]]:
        mapped: list[dict[str, Any]] = []
        for issue in issues:
            severity = "blocking" if issue.get("severity") == "error" else issue.get("severity", "warning")
            mapped.append({"severity": severity, "code": issue.get("code", "VALIDATION_ISSUE"), "message": issue.get("message", "Validation issue"), "path": issue.get("path") or default_path, "details": issue})
        return mapped


class InterfaceCompilerTool:
    def compile(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        compiled = InterfaceCompiler().compile(scene_doc, specs)
        return {
            "schema_type": "CompiledInterfaceIndex",
            "scene_revision": compiled.get("scene_revision", scene_doc.get("revision", 0)),
            "physical_bindings": compiled.get("compiled_physical_edges", []),
            "signal_bindings": compiled.get("compiled_signal_edges", []),
            "warnings": compiled.get("warnings", []),
        }


class TopologyBuilderTool:
    def build(self, scene_doc: dict[str, Any], capability_index: dict[str, Any] | None, specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        graph = TopologyBuilder().build(scene_doc, specs)
        graph["capability_index_summary"] = (capability_index or {}).get("counts", {})
        return graph


class ReachabilityChecker:
    def check(self, topology_graph: dict[str, Any], source: str, target: str, material_class: str | None = None, graph: str = "process_graph") -> dict[str, Any]:
        reachable = TopologyBuilder().is_reachable(topology_graph, source, target, graph)
        return {"reachable": reachable, "source": source, "target": target, "graph": graph, "material_class": material_class, "reason": None if reachable else "no_path_in_graph"}


class SchemaValidator:
    def validate(self, artifact: AgentArtifactContract | dict[str, Any]) -> ValidationReport:
        from app.agent.contracts import ArtifactSchemaValidator

        return ArtifactSchemaValidator().validate_artifact(artifact)


class ReferenceValidator:
    def validate(self, artifact: AgentArtifactContract, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> ValidationReport:
        if not artifact.artifact_type.endswith("_patch"):
            return ValidationReport(summary={"artifact_type": artifact.artifact_type})
        envelope = PatchEnvelope.model_validate(artifact.payload)
        return GuardianValidator().validate_patch(artifact.artifact_type, envelope, scene_doc, specs)


class PortCompatibilityValidator:
    def validate_edges(self, edges: list[dict[str, Any]], scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], edge_kind: str) -> ValidationReport:
        draft = deepcopy(scene_doc)
        section = {"physical": "physical_edges", "process": "process_edges", "signal": "signal_edges"}[edge_kind]
        draft[section] = list(draft.get(section, [])) + edges
        envelope = PatchEnvelope(
            artifact_type={"physical": "physical_edge_patch", "process": "process_patch", "signal": "signal_patch"}[edge_kind],  # type: ignore[arg-type]
            base_scene_revision=int(scene_doc.get("revision", 0)),
            operations=[{"op": "add", "path": f"/{section}/-", "value": edge} for edge in edges],
            reason="Validate edge compatibility.",
            confidence=1.0,
        )
        return GuardianValidator().validate_patch(envelope.artifact_type, envelope, scene_doc, specs)


class BehaviorClosureValidator:
    def validate(self, scene_behavior_graph: dict[str, Any]) -> ValidationReport:
        return GuardianValidator().validate_behavior_graph(scene_behavior_graph)


class RuntimePreflightValidator:
    def validate(self, scene_behavior_graph: dict[str, Any], runtime_snapshot: dict[str, Any] | None = None) -> ValidationReport:
        report = GuardianValidator().validate_behavior_graph(scene_behavior_graph)
        issues = [issue.model_dump(mode="json") for issue in report.issues]
        snapshot = runtime_snapshot or scene_behavior_graph.get("state_model", {})
        if scene_behavior_graph.get("behavior_rules") and not snapshot.get("device_states"):
            issues.append({"severity": "blocking", "code": "PREFLIGHT_DEVICE_STATES_MISSING", "message": "Runtime preflight needs initial device_states.", "path": "state_model.device_states"})
        if scene_behavior_graph.get("event_bus", {}).get("events") and not scene_behavior_graph.get("failure_observations"):
            issues.append({"severity": "warning", "code": "PREFLIGHT_FAILURE_OBSERVATIONS_MISSING", "message": "Runtime graph has no failure observations for timeout/deadlock handling.", "path": "failure_observations"})
        return ValidationReport.from_issues(issues, {"preflight": True, **report.summary})


class IntentSchemaTool:
    def parse(self, user_message: str) -> dict[str, Any]:
        return IntentParser().parse(user_message)


class ProcessTemplateLibrary:
    TEMPLATES = {
        "source": {"template_id": "source", "required_ports": ["flow_output"], "description": "Material source handoff."},
        "buffered_transport": {"template_id": "buffered_transport", "required_ports": ["flow_input", "flow_output"], "description": "Conveyor or queue transport with backpressure."},
        "machine_process": {"template_id": "machine_process", "required_ports": ["flow_input", "flow_output"], "description": "Timed process step."},
        "robot_pick_place": {"template_id": "robot_pick_place", "required_ports": ["flow_input", "flow_output"], "description": "Robot pick-place with resource locks."},
        "sorting": {"template_id": "sorting", "required_ports": ["flow_input"], "description": "Route by material class or policy."},
        "backpressure": {"template_id": "backpressure", "required_ports": ["capacity_available", "blocked"], "description": "Pause upstream when downstream is full."},
    }

    def list_templates(self) -> list[dict[str, Any]]:
        return list(self.TEMPLATES.values())

    def get(self, template_id: str) -> dict[str, Any] | None:
        return self.TEMPLATES.get(template_id)


class EventBusBuilder:
    def build_routes(self, signal_edges: list[dict[str, Any]]) -> dict[str, Any]:
        events = []
        routes = []
        seen = set()
        for edge in signal_edges:
            for endpoint in [edge.get("source"), edge.get("target")]:
                if endpoint and endpoint not in seen:
                    events.append({"event_id": endpoint, "source": endpoint, "payload_schema": {"type": "object"}})
                    seen.add(endpoint)
            if edge.get("source") and edge.get("target"):
                routes.append({"route_id": edge.get("route_id") or new_id("route"), "from": edge["source"], "to": {"type": "event", "id": edge["target"]}})
        return {"events": events, "topics": [], "routes": routes, "subscriptions": {}}


class PolicyLibrary:
    def resource_lock(self, instance_id: str, behavior_id: str, resources: list[str]) -> dict[str, Any]:
        return {"policy_id": f"resource_lock_{instance_id}_{behavior_id}", "type": "resource_lock", "instance_id": instance_id, "behavior_id": behavior_id, "resources": resources}

    def queue_wait(self, queue_id: str, capacity: int) -> dict[str, Any]:
        return {"policy_id": f"queue_wait_{queue_id}", "type": "queue_wait", "queue_id": queue_id, "capacity": capacity}

    def deadlock_detection(self, timeout_s: float = 30.0) -> dict[str, Any]:
        return {"policy_id": "deadlock_detection", "type": "deadlock_detection", "timeout_s": timeout_s, "on_detected": "raise_observation"}


class PhysicalEdgePatchWriter:
    def write(self, scene_doc: dict[str, Any], candidates: list[dict[str, Any]]) -> AgentArtifactContract | None:
        if not candidates:
            return None
        return patch_artifact(
            "physical_edge_patch",
            int(scene_doc.get("revision", 0)),
            [{"op": "add", "path": "/physical_edges/-", "value": edge} for edge in candidates],
            "Stage physical edge candidates.",
            min(edge.get("confidence", 0.5) for edge in candidates),
            approval_required=any(edge.get("confidence", 0) < 0.75 for edge in candidates),
            source_trace=[{"kind": "implicit_edge_candidates", "count": len(candidates)}],
        )


class ProcessPatchWriter:
    def write(self, scene_doc: dict[str, Any], process_edges: list[dict[str, Any]]) -> AgentArtifactContract | None:
        if not process_edges:
            return None
        return patch_artifact("process_patch", int(scene_doc.get("revision", 0)), [{"op": "add", "path": "/process_edges/-", "value": edge} for edge in process_edges], "Stage process edge candidates.", 0.76, approval_required=False)


class SignalPatchWriter:
    def write(self, scene_doc: dict[str, Any], signal_edges: list[dict[str, Any]]) -> AgentArtifactContract | None:
        if not signal_edges:
            return None
        return patch_artifact("signal_patch", int(scene_doc.get("revision", 0)), [{"op": "add", "path": "/signal_edges/-", "value": edge} for edge in signal_edges], "Stage signal route candidates.", 0.8, approval_required=False, risk="low")


class TopologyWriter:
    def write_candidates(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[AgentArtifactContract]:
        return topology_completion_artifacts(scene_doc, specs)


class ApprovalManager:
    def decision_for(self, artifact: AgentArtifactContract) -> dict[str, Any]:
        return {
            "approval_required": artifact.approval_required,
            "reason": "low_confidence_or_medium_risk" if artifact.approval_required else "safe_to_stage",
            "confidence": artifact.confidence,
        }


class IntentParser:
    def parse(self, user_message: str, *, simulation_run_id: str | None = None, document_text: str | None = None) -> dict[str, Any]:
        text = user_message.lower()
        if any(token in text for token in ["方案", "比较", "优化", "产能", "吞吐", "瓶颈", "variant"]):
            intent_type = "scenario_compare"
        elif simulation_run_id or any(token in text for token in ["报错", "诊断", "为什么", "deadlock", "timeout", "卡住", "堵"]):
            intent_type = "runtime_diagnosis"
        elif document_text or any(token in text for token in ["process time", "cycle time", "节拍", "速度", "容量", "参数", "45s"]):
            intent_type = "parameter_fill"
        elif any(token in text for token in ["补齐", "拓扑", "连线", "路由", "只有位置", "信号"]):
            intent_type = "topology_completion"
        elif any(token in text for token in ["抓", "机器人", "行为图", "scenebehaviorgraph", "传送带末端"]):
            intent_type = "behavior_graph"
        else:
            intent_type = "query_scene"
        return {"intent_type": intent_type, "confidence": 0.72, "raw_text": user_message, "simulation_run_id": simulation_run_id}


class SlotResolver:
    def resolve(self, scene_doc: dict[str, Any], topology: dict[str, Any] | None, user_message: str) -> dict[str, Any]:
        text = user_message.lower()
        instances = scene_doc.get("instances", [])
        mentioned = [instance.get("instance_id") for instance in instances if instance.get("instance_id", "").lower() in text]
        device_type_mentions = [instance.get("instance_id") for instance in instances if instance.get("device_type", "").lower() in text]
        rack_slot = next((match.group(0).upper() for match in re.finditer(r"[a-z][0-9]+", user_message, re.IGNORECASE)), None)
        return {
            "mentioned_instances": list(dict.fromkeys(mentioned + device_type_mentions)),
            "rack_slot": rack_slot,
            "topology_graph_id": (topology or {}).get("graph_id"),
        }


class ParameterExtractor:
    PARAM_PATTERNS = [
        ("process_time_s", re.compile(r"(?:process\s*time|cycle\s*time|节拍|处理时间)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(s|sec|second|seconds|秒|min|分钟)?", re.I)),
        ("speed_mps", re.compile(r"(?:speed|速度)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(m/s|米/秒|mps)?", re.I)),
        ("capacity", re.compile(r"(?:capacity|容量|缓存)\s*[=:：]?\s*(\d+)", re.I)),
        ("throughput_per_hour", re.compile(r"(?:throughput|吞吐|产能)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(/h|per hour|件/小时|小时)?", re.I)),
    ]

    def extract(self, text: str) -> list[dict[str, Any]]:
        params: list[dict[str, Any]] = []
        for name, pattern in self.PARAM_PATTERNS:
            for match in pattern.finditer(text):
                raw_value = float(match.group(1))
                unit = match.group(2) if (match.lastindex or 0) >= 2 else None
                unit = unit or self._default_unit(name)
                value = self._normalize_value(name, raw_value, unit)
                params.append(
                    {
                        "name": name,
                        "value": value,
                        "raw_value": match.group(0),
                        "unit": self._default_unit(name),
                        "confidence": 0.82,
                        "source_trace": {"kind": "text_span", "start": match.start(), "end": match.end(), "text": match.group(0)},
                    }
                )
        return params

    @staticmethod
    def _default_unit(name: str) -> str:
        return {"process_time_s": "s", "speed_mps": "m/s", "capacity": "count", "throughput_per_hour": "items/hour"}[name]

    @staticmethod
    def _normalize_value(name: str, value: float, unit: str) -> float | int:
        if name == "process_time_s" and unit.lower() in {"min", "分钟"}:
            return value * 60
        if name == "capacity":
            return int(value)
        return value


class ParameterBinder:
    def bind(self, params: list[dict[str, Any]], scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        bindings: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for param in params:
            target = self._target_for_param(param["name"], scene_doc, specs)
            if not target:
                missing.append({"param": param, "reason": "no_compatible_target"})
                continue
            bindings.append({"param": param, "target": target, "confidence": min(0.8, param.get("confidence", 0.7))})
        return {"extracted_params": params, "target_bindings": bindings, "units_normalized": True, "missing_params": missing}

    @staticmethod
    def _target_for_param(name: str, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        for index, instance in enumerate(scene_doc.get("instances", [])):
            spec = specs.get(instance.get("spec_id"), {})
            params_schema = spec.get("params_schema", {})
            if name in params_schema:
                return {"path": f"/instances/{index}/param_overrides/{name}", "instance_id": instance.get("instance_id"), "field": name}
            if name == "process_time_s" and instance.get("device_type") not in {"workpiece", "workpiece_carrier"}:
                return {"path": f"/instances/{index}/param_overrides/{name}", "instance_id": instance.get("instance_id"), "field": name}
        return None


def patch_artifact(artifact_type: str, base_revision: int, operations: list[dict[str, Any]], reason: str, confidence: float, *, approval_required: bool, source_trace: list[dict[str, Any]] | None = None, risk: str = "medium") -> AgentArtifactContract:
    envelope = PatchEnvelope(
        artifact_type=artifact_type,  # type: ignore[arg-type]
        base_scene_revision=base_revision,
        operations=operations,
        reason=reason,
        confidence=confidence,
        approval_required=approval_required,
        rollback_hint="Scene revision can be restored from scene_events before this patch.",
        source_trace=source_trace or [],
        risk=risk,  # type: ignore[arg-type]
    )
    return AgentArtifactContract(
        artifact_type=artifact_type,  # type: ignore[arg-type]
        base_scene_revision=base_revision,
        payload=envelope.model_dump(mode="json"),
        confidence=confidence,
        approval_required=approval_required,
        source_trace=source_trace or [],
    )


def behavior_graph_artifact(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], topology: dict[str, Any] | None, user_message: str) -> AgentArtifactContract:
    graph = BehaviorGraphBuilder().build(scene_doc, specs, topology, user_message)
    validation = GuardianValidator().validate_behavior_graph(graph)
    operation = {"op": "replace", "path": "/derived_artifacts/scene_behavior_graph", "value": {"status": "candidate", "graph": graph}}
    artifact = patch_artifact(
        "scene_behavior_graph_patch",
        int(scene_doc.get("revision", 0)),
        [operation],
        "Compile a runtime-consumable SceneBehaviorGraph from current signal and process facts.",
        0.78 if validation.valid else 0.4,
        approval_required=False,
        source_trace=[{"kind": "scene", "scene_id": scene_doc.get("scene_id"), "revision": scene_doc.get("revision", 0)}],
        risk="low",
    )
    artifact.validation_report = validation
    return artifact


def topology_completion_artifacts(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[AgentArtifactContract]:
    candidates = ImplicitEdgeCandidateGenerator().generate(scene_doc, specs)
    selected_physical = candidates[: max(1, min(6, len(candidates)))]
    process_edges = ProcessEdgePlanner().plan_from_physical(scene_doc, specs, selected_physical)
    signal_edges = SignalRoutePlanner().plan(scene_doc, specs, process_edges)
    base_revision = int(scene_doc.get("revision", 0))
    artifacts: list[AgentArtifactContract] = []
    if selected_physical:
        artifacts.append(
            patch_artifact(
                "physical_edge_patch",
                base_revision,
                [{"op": "add", "path": "/physical_edges/-", "value": edge} for edge in selected_physical],
                "Infer missing physical material connections from device positions and interface compatibility.",
                min(edge["confidence"] for edge in selected_physical),
                approval_required=any(edge.get("confidence", 0) < 0.75 for edge in selected_physical),
                source_trace=[{"kind": "geometry", "candidate_count": len(candidates)}],
                risk="medium",
            )
        )
    if process_edges:
        artifacts.append(
            patch_artifact(
                "process_patch",
                base_revision,
                [{"op": "add", "path": "/process_edges/-", "value": edge} for edge in process_edges],
                "Derive process material-flow edges from inferred physical interface connections.",
                min(edge.get("confidence", 0.6) for edge in process_edges),
                approval_required=any(edge.get("confidence", 0) < 0.75 for edge in process_edges),
                source_trace=[{"kind": "physical_edge_candidates", "edge_ids": [edge["edge_id"] for edge in selected_physical]}],
                risk="medium",
            )
        )
    if signal_edges:
        artifacts.append(
            patch_artifact(
                "signal_patch",
                base_revision,
                [{"op": "add", "path": "/signal_edges/-", "value": edge} for edge in signal_edges],
                "Compile signal routes and event handshakes from process edges and DeviceSpec interface bindings.",
                0.8,
                approval_required=False,
                source_trace=[{"kind": "interface_compiler", "process_edges": [edge.get("edge_id") for edge in process_edges or scene_doc.get("process_edges", [])]}],
                risk="low",
            )
        )
    validator = GuardianValidator()
    for artifact in artifacts:
        envelope = PatchEnvelope.model_validate(artifact.payload)
        artifact.validation_report = validator.validate_patch(artifact.artifact_type, envelope, scene_doc, specs)
    return artifacts


def parameter_binding_artifact(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], text: str) -> AgentArtifactContract | None:
    params = ParameterExtractor().extract(text)
    if not params:
        return None
    plan = ParameterBinder().bind(params, scene_doc, specs)
    operations = [
        {"op": "add", "path": binding["target"]["path"], "value": binding["param"]["value"]}
        for binding in plan["target_bindings"]
    ]
    if not operations:
        return AgentArtifactContract(
            artifact_type="question_set",
            base_scene_revision=int(scene_doc.get("revision", 0)),
            payload={"questions": [{"question_id": "missing_parameter_target", "prompt": "无法确定参数绑定到哪个设备，请指定目标设备。", "params": params}]},
            confidence=0.35,
            approval_required=True,
        )
    artifact = patch_artifact(
        "parameter_binding_patch",
        int(scene_doc.get("revision", 0)),
        operations,
        "Bind extracted document/user parameters into SceneDocument instance param_overrides.",
        min(binding.get("confidence", 0.7) for binding in plan["target_bindings"]),
        approval_required=any(binding.get("confidence", 0) < 0.75 for binding in plan["target_bindings"]),
        source_trace=[param["source_trace"] for param in params],
        risk="medium",
    )
    artifact.payload["parameter_binding_plan"] = plan
    return artifact


def readonly_diagnostic_artifact(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], topology: dict[str, Any] | None) -> AgentArtifactContract:
    missing_sections = [section for section in ["physical_edges", "process_edges", "signal_edges"] if not scene_doc.get(section)]
    topology_warnings = (topology or {}).get("warnings", [])
    report = {
        "symptom": "scene_context_loaded",
        "root_causes": [f"missing_{section}" for section in missing_sections],
        "evidence": {
            "scene_id": scene_doc.get("scene_id"),
            "revision": scene_doc.get("revision", 0),
            "instance_count": len(scene_doc.get("instances", [])),
            "device_spec_count": len(specs),
            "topology_warning_count": len(topology_warnings),
            "topology_warnings": topology_warnings[:10],
        },
        "suggested_repairs": [
            {"repair_type": "topology_completion", "reason": "Scene has device positions but incomplete physical/process/signal edges."}
            for _ in missing_sections[:1]
        ],
        "can_auto_repair": bool(scene_doc.get("instances") and missing_sections),
    }
    return AgentArtifactContract(
        artifact_type="diagnostic_report",
        base_scene_revision=int(scene_doc.get("revision", 0)),
        payload=report,
        confidence=0.9,
        approval_required=False,
        source_trace=[{"kind": "scene", "scene_id": scene_doc.get("scene_id"), "revision": scene_doc.get("revision", 0)}],
    )


def build_topology(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return TopologyBuilder().build(scene_doc, specs)
