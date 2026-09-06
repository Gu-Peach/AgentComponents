from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from app.services.ids import new_id


class TopologyBuilder:
    """Build the derived TopologyGraph from SceneDocument and DeviceSpec facts."""

    def build(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        nodes = self._build_nodes(scene_doc, specs)
        physical_graph = self._edge_graph(scene_doc.get("physical_edges", []), "physical")
        process_graph = self._edge_graph(scene_doc.get("process_edges", []), "process")
        signal_graph = self._edge_graph(scene_doc.get("signal_edges", []), "signal")
        transport_graph = self._build_transport_graph(scene_doc, specs)
        warnings = self._warnings(scene_doc, specs)
        graph_id = f"topology_{scene_doc.get('scene_id', new_id('scene'))}_r{scene_doc.get('revision', 0)}"
        return {
            "schema_id": "topology_graph_runtime_v0_1",
            "schema_type": "TopologyGraph",
            "version": "0.1.0",
            "graph_id": graph_id,
            "source_scene": {
                "scene_id": scene_doc.get("scene_id"),
                "scene_revision": scene_doc.get("revision", 0),
                "compiled_at": datetime.now(timezone.utc).isoformat(),
            },
            "compiler": {"name": "backend.topology_builder", "version": "0.1.0", "mode": "explicit_edges_only"},
            "nodes": nodes,
            "physical_graph": physical_graph,
            "process_graph": process_graph,
            "signal_graph": signal_graph,
            "transport_graph": transport_graph,
            "warnings": warnings,
        }

    def is_reachable(self, topology: dict[str, Any], source: str, target: str, graph: str = "process_graph") -> bool:
        edges = topology.get(graph, {}).get("edges", [])
        adjacency: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            adjacency[edge.get("source")].append(edge.get("target"))
        seen = {source}
        queue: deque[str] = deque([source])
        while queue:
            node = queue.popleft()
            if node == target:
                return True
            for nxt in adjacency.get(node, []):
                if nxt and nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        return False

    def _build_nodes(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        nodes: list[dict[str, Any]] = []
        for instance in scene_doc.get("instances", []):
            instance_id = instance.get("instance_id")
            spec = specs.get(instance.get("spec_id"), {})
            nodes.append(
                {
                    "node_id": instance_id,
                    "node_type": "device_instance",
                    "instance_id": instance_id,
                    "spec_id": instance.get("spec_id"),
                    "device_type": instance.get("device_type"),
                    "world_frame": instance.get("transform"),
                }
            )
            for port in spec.get("physical_interfaces", []):
                nodes.append({"node_id": f"{instance_id}.{port.get('interface_id')}", "node_type": "physical_interface", "instance_id": instance_id, "interface_id": port.get("interface_id"), "metadata": port})
            for port in spec.get("process_ports", []):
                nodes.append({"node_id": f"{instance_id}.{port.get('port_id')}", "node_type": "process_port", "instance_id": instance_id, "port_id": port.get("port_id"), "metadata": port})
            for port in spec.get("signal_ports", []):
                nodes.append({"node_id": f"{instance_id}.{port.get('port_id')}", "node_type": "signal_port", "instance_id": instance_id, "port_id": port.get("port_id"), "metadata": port})
        for material in scene_doc.get("materials", []):
            nodes.append({"node_id": material.get("material_id"), "node_type": "material", "metadata": material})
        return nodes

    @staticmethod
    def _edge_graph(edges: list[dict[str, Any]], graph_type: str) -> dict[str, Any]:
        return {
            "nodes": sorted({endpoint for edge in edges for endpoint in [edge.get("source"), edge.get("target")] if endpoint}),
            "edges": [{**edge, "status": edge.get("status", "valid"), "graph_type": graph_type} for edge in edges],
        }

    @staticmethod
    def _build_transport_graph(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        links: list[dict[str, Any]] = []
        instance_specs = {item.get("instance_id"): specs.get(item.get("spec_id"), {}) for item in scene_doc.get("instances", [])}
        for edge in scene_doc.get("process_edges", []):
            target_instance = edge.get("target", "").split(".", 1)[0]
            target_spec = instance_specs.get(target_instance, {})
            behavior = next(iter(target_spec.get("transport_behaviors", [])), {})
            links.append(
                {
                    "link_id": f"transport_{edge.get('edge_id')}",
                    "source": edge.get("source"),
                    "target": edge.get("target"),
                    "implementer": target_instance,
                    "status": "valid" if behavior else "warning",
                    "source_process_edge": edge.get("edge_id"),
                    "required_behavior": behavior.get("behavior_id"),
                    "material_classes": edge.get("material_classes", []),
                    "signal_interlocks": edge.get("compiled_signal_edges", []),
                }
            )
        return {"nodes": sorted({item for link in links for item in [link.get("source"), link.get("target")] if item}), "links": links}

    @staticmethod
    def _warnings(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        warnings: list[dict[str, Any]] = []
        instance_specs = {item.get("instance_id"): specs.get(item.get("spec_id")) for item in scene_doc.get("instances", [])}
        for instance_id, spec in instance_specs.items():
            if not spec:
                warnings.append({"warning_id": new_id("warn"), "severity": "error", "message": f"Missing DeviceSpec for {instance_id}", "instance_id": instance_id})
                continue
            for port in spec.get("process_ports", []):
                ref = f"{instance_id}.{port.get('port_id')}"
                connected = any(ref in {edge.get("source"), edge.get("target")} for edge in scene_doc.get("process_edges", []))
                if not connected:
                    warnings.append({"warning_id": new_id("warn"), "severity": "info", "message": f"Process port is not connected: {ref}", "graph": "process_graph", "port_id": ref})
            for port in spec.get("signal_ports", []):
                if port.get("direction") not in {"output", "bidirectional"}:
                    continue
                ref = f"{instance_id}.{port.get('port_id')}"
                consumed = any(edge.get("source") == ref for edge in scene_doc.get("signal_edges", []))
                if not consumed:
                    warnings.append({"warning_id": new_id("warn"), "severity": "info", "message": f"Signal output has no consumers: {ref}", "graph": "signal_graph", "port_id": ref})
        return warnings

