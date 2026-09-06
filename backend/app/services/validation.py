from __future__ import annotations

from typing import Any


Endpoint = tuple[str, str]


def parse_endpoint(endpoint: str) -> Endpoint:
    if "." not in endpoint:
        raise ValueError(f"Endpoint must use instance_id.port_id format: {endpoint}")
    instance_id, port_id = endpoint.split(".", 1)
    if not instance_id or not port_id:
        raise ValueError(f"Endpoint must use instance_id.port_id format: {endpoint}")
    return instance_id, port_id


def index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {item[key]: item for item in items if key in item}


def specs_by_id(specs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {spec.get("device_spec_id") or spec.get("schema_id"): spec for spec in specs}


def build_scene_context(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    instance_index = index_by(scene_doc.get("instances", []), "instance_id")
    return {"scene": scene_doc, "specs": specs, "instance_index": instance_index}


def resolve_port(ctx: dict[str, Any], endpoint: str, section: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    instance_id, port_id = parse_endpoint(endpoint)
    instance = ctx["instance_index"].get(instance_id)
    if not instance:
        raise ValueError(f"Unknown instance: {instance_id}")
    spec = ctx["specs"].get(instance.get("spec_id"))
    if not spec:
        raise ValueError(f"DeviceSpec not found for instance {instance_id}: {instance.get('spec_id')}")
    key = "interface_id" if section == "physical_interfaces" else "port_id"
    ports = index_by(spec.get(section, []), key)
    port = ports.get(port_id)
    if not port:
        raise ValueError(f"{section}.{port_id} not found on {instance.get('spec_id')}")
    return instance, spec, port


def validate_process_edge(ctx: dict[str, Any], source: str, target: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        _, _, source_port = resolve_port(ctx, source, "process_ports")
        _, _, target_port = resolve_port(ctx, target, "process_ports")
        if source_port.get("direction") not in {"output", "bidirectional"}:
            issues.append({"severity": "error", "code": "PROCESS_SOURCE_DIRECTION", "message": "Process edge source must be output/bidirectional."})
        if target_port.get("direction") not in {"input", "bidirectional"}:
            issues.append({"severity": "error", "code": "PROCESS_TARGET_DIRECTION", "message": "Process edge target must be input/bidirectional."})
    except ValueError as exc:
        issues.append({"severity": "error", "code": "INVALID_PROCESS_ENDPOINT", "message": str(exc)})
    return issues


def validate_physical_edge(ctx: dict[str, Any], source: str, target: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        _, _, source_port = resolve_port(ctx, source, "physical_interfaces")
        _, _, target_port = resolve_port(ctx, target, "physical_interfaces")
        if source_port.get("direction") not in {"output", "bidirectional"}:
            issues.append({"severity": "error", "code": "PHYSICAL_SOURCE_DIRECTION", "message": "Physical edge source must be output/bidirectional."})
        if target_port.get("direction") not in {"input", "bidirectional"}:
            issues.append({"severity": "error", "code": "PHYSICAL_TARGET_DIRECTION", "message": "Physical edge target must be input/bidirectional."})
        source_classes = set(source_port.get("material_classes", []))
        target_classes = set(target_port.get("material_classes", []))
        if source_classes and target_classes and source_classes.isdisjoint(target_classes):
            issues.append({"severity": "error", "code": "MATERIAL_CLASS_MISMATCH", "message": "Physical edge material classes are incompatible."})
    except ValueError as exc:
        issues.append({"severity": "error", "code": "INVALID_PHYSICAL_ENDPOINT", "message": str(exc)})
    return issues


def validate_signal_edge(ctx: dict[str, Any], source: str, target: str, transform: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    try:
        _, _, source_port = resolve_port(ctx, source, "signal_ports")
        _, _, target_port = resolve_port(ctx, target, "signal_ports")
        if source_port.get("direction") not in {"output", "bidirectional"}:
            issues.append({"severity": "error", "code": "SIGNAL_SOURCE_DIRECTION", "message": "Signal edge source must be output/bidirectional."})
        if target_port.get("direction") not in {"input", "bidirectional"}:
            issues.append({"severity": "error", "code": "SIGNAL_TARGET_DIRECTION", "message": "Signal edge target must be input/bidirectional."})
        if source_port.get("value_type") != target_port.get("value_type") and (not transform or transform.get("type") == "identity"):
            issues.append({"severity": "error", "code": "SIGNAL_VALUE_TYPE_MISMATCH", "message": "Signal value types differ; provide an explicit transform."})
    except ValueError as exc:
        issues.append({"severity": "error", "code": "INVALID_SIGNAL_ENDPOINT", "message": str(exc)})
    return issues


def raise_if_errors(issues: list[dict[str, Any]]) -> None:
    errors = [issue for issue in issues if issue.get("severity") == "error"]
    if errors:
        raise ValueError(errors[0]["message"])
