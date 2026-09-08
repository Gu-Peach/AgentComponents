from __future__ import annotations

from typing import Any

from app.services.ids import new_id
from app.services.validation import resolve_port, validate_process_edge, validate_signal_edge


def _bindings_by_process_port(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        binding.get("process_port"): binding
        for binding in spec.get("interface_bindings", [])
        if binding.get("process_port")
    }


def _signal_ports_by_id(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {port.get("port_id"): port for port in spec.get("signal_ports", []) if port.get("port_id")}


def _binding_signal_ports(binding: dict[str, Any] | None, process_port: dict[str, Any]) -> list[str]:
    signal_ids = (binding or {}).get("signal_ports") or process_port.get("bound_signal_ports", [])
    return list(dict.fromkeys(signal_ids))


def _edge_exists(edges: list[dict[str, Any]], source: str, target: str) -> bool:
    return any(edge.get("source") == source and edge.get("target") == target for edge in edges)


def _signal_pair_allowed(source_signal_id: str, target_signal_id: str) -> bool:
    source = source_signal_id.lower()
    target = target_signal_id.lower()
    if any(token in target for token in ["start", "accept"]):
        return any(token in source for token in ["ready", "available", "done", "arrived"])
    if any(token in target for token in ["pause", "stop"]):
        return any(token in source for token in ["blocked", "error", "full"])
    if any(token in target for token in ["resume", "release"]):
        return any(token in source for token in ["available", "released", "ready", "done"])
    if any(token in target for token in ["move", "rotate"]):
        return any(token in source for token in ["ready", "available", "done"])
    return source == target


class InterfaceCompiler:
    """Compile process-level wiring into runtime signal wiring.

    VC spreads this across vcFlow/vcConnector connections, vcSimInterface matching,
    and TransportSystem links. This compiler keeps the same split explicit for the
    backend: process edges describe material-flow intent, signal edges describe
    runtime event routing, and physical edges stay reserved for real model/device
    connection anchors. Legacy specs can still opt in to physical-edge generation
    by explicitly binding both process ports to physical interfaces.
    """

    def compile(self, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
        ctx = {
            "scene": scene_doc,
            "specs": specs,
            "instance_index": {item.get("instance_id"): item for item in scene_doc.get("instances", [])},
        }
        compiled_physical_edges: list[dict[str, Any]] = []
        compiled_signal_edges: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []

        for process_edge in scene_doc.get("process_edges", []):
            issues = validate_process_edge(ctx, process_edge.get("source", ""), process_edge.get("target", ""))
            if any(issue.get("severity") == "error" for issue in issues):
                warnings.extend({**issue, "process_edge_id": process_edge.get("edge_id")} for issue in issues)
                continue

            source_instance, source_spec, source_port = resolve_port(ctx, process_edge["source"], "process_ports")
            target_instance, target_spec, target_port = resolve_port(ctx, process_edge["target"], "process_ports")
            source_binding = _bindings_by_process_port(source_spec).get(source_port["port_id"])
            target_binding = _bindings_by_process_port(target_spec).get(target_port["port_id"])

            source_physical_id = (source_binding or {}).get("physical_interface")
            target_physical_id = (target_binding or {}).get("physical_interface")
            if source_physical_id and target_physical_id:
                source_physical = f"{source_instance['instance_id']}.{source_physical_id}"
                target_physical = f"{target_instance['instance_id']}.{target_physical_id}"
                if not _edge_exists(scene_doc.get("physical_edges", []), source_physical, target_physical):
                    compiled_physical_edges.append(
                        {
                            "edge_id": f"phys_{process_edge.get('edge_id', new_id('edge'))}",
                            "source": source_physical,
                            "target": target_physical,
                            "edge_type": "physical_connection",
                            "connection_method": "compiled_from_process",
                            "compiled_from": process_edge.get("edge_id"),
                            "is_inferred": True,
                            "confidence": 0.8,
                            "compatibility_result": {"status": "not_checked", "matched_fields": [], "missing_fields": []},
                            "snap_result": {
                                "distance_m": None,
                                "angle_deg": None,
                                "within_tolerance": "not_checked",
                                "retain_offset": False,
                            },
                        }
                    )
            else:
                warnings.append(
                    {
                        "severity": "warning",
                        "code": "PROCESS_EDGE_HAS_NO_PHYSICAL_BINDING",
                        "message": "Process edge has no explicit physical-interface binding; only signal routing will be compiled.",
                        "process_edge_id": process_edge.get("edge_id"),
                    }
                )

            source_signals = _signal_ports_by_id(source_spec)
            target_signals = _signal_ports_by_id(target_spec)
            source_signal_ids = _binding_signal_ports(source_binding, source_port)
            target_signal_ids = _binding_signal_ports(target_binding, target_port)
            for source_signal_id in source_signal_ids:
                source_signal = source_signals.get(source_signal_id)
                if not source_signal or source_signal.get("direction") not in {"output", "bidirectional"}:
                    continue
                for target_signal_id in target_signal_ids:
                    target_signal = target_signals.get(target_signal_id)
                    if not target_signal or target_signal.get("direction") not in {"input", "bidirectional"}:
                        continue
                    if not _signal_pair_allowed(source_signal_id, target_signal_id):
                        continue
                    source_ref = f"{source_instance['instance_id']}.{source_signal_id}"
                    target_ref = f"{target_instance['instance_id']}.{target_signal_id}"
                    transform = {"type": "identity"}
                    if source_signal.get("value_type") != target_signal.get("value_type"):
                        transform = {
                            "type": "payload_template",
                            "payload_template": {
                                "source_signal": source_ref,
                                "target_signal": target_ref,
                                "source_value": "${value}",
                            },
                        }
                    if validate_signal_edge(ctx, source_ref, target_ref, transform):
                        continue
                    if not _edge_exists(scene_doc.get("signal_edges", []), source_ref, target_ref):
                        compiled_signal_edges.append(
                            {
                                "edge_id": f"sig_{process_edge.get('edge_id', new_id('edge'))}_{source_signal_id}_to_{target_signal_id}",
                                "source": source_ref,
                                "target": target_ref,
                                "edge_type": "control_signal",
                                "delivery": "event" if target_signal.get("value_type") == "event" else "command",
                                "trigger": source_signal.get("edge_trigger", "on_rising_edge"),
                                "transform": transform,
                                "timeout_ms": 30000,
                                "on_timeout": "raise_observation",
                                "enabled": True,
                                "compiled_from": process_edge.get("edge_id"),
                                "route_id": f"route_sig_{process_edge.get('edge_id', new_id('edge'))}_{source_signal_id}_to_{target_signal_id}",
                            }
                        )

        return {
            "scene_revision": scene_doc.get("revision", 0),
            "compiled_physical_edges": compiled_physical_edges,
            "compiled_signal_edges": compiled_signal_edges,
            "warnings": warnings,
        }
