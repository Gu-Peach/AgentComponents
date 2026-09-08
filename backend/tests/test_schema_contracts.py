from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_SCHEMA_ROOT = REPO_ROOT / "docs" / "business" / "SimulationSchema"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ids(items: list[dict[str, Any]], key: str) -> list[str]:
    return [item[key] for item in items if key in item]


def assert_unique(values: list[str], label: str) -> None:
    duplicates = [value for value, count in Counter(values).items() if count > 1]
    assert not duplicates, f"duplicate {label}: {duplicates}"


def assert_local_frame(item: dict[str, Any], label: str) -> None:
    local_frame = item.get("local_frame")
    assert isinstance(local_frame, dict), f"{label} missing local_frame"
    position = local_frame.get("position")
    assert isinstance(position, list) and len(position) == 3, f"{label} has invalid local_frame.position"
    assert all(isinstance(value, (int, float)) for value in position), f"{label} position must be numeric"
    assert local_frame.get("rotation_euler") is not None or local_frame.get("forward") is not None, f"{label} needs rotation_euler or forward"


def assert_device_spec_contract(spec: dict[str, Any]) -> None:
    for section in [
        "asset",
        "params_schema",
        "physical_interfaces",
        "process_ports",
        "signal_ports",
        "interface_bindings",
        "transport_behaviors",
        "runtime_contract",
        "type_specific_contract",
    ]:
        assert section in spec, f"{spec.get('device_spec_id')} missing {section}"

    physical_interfaces = spec.get("physical_interfaces", [])
    process_ports = spec.get("process_ports", [])
    signal_ports = spec.get("signal_ports", [])
    bindings = spec.get("interface_bindings", [])
    behaviors = spec.get("transport_behaviors", [])

    physical_ids = set(ids(physical_interfaces, "interface_id"))
    process_ids = set(ids(process_ports, "port_id"))
    signal_ids = set(ids(signal_ports, "port_id"))
    behavior_ids = set(ids(behaviors, "behavior_id"))

    assert_unique(list(physical_ids), "physical_interfaces")
    assert_unique(list(process_ids), "process_ports")
    assert_unique(list(signal_ids), "signal_ports")
    assert_unique(list(behavior_ids), "transport_behaviors")

    for interface in physical_interfaces:
        assert {"interface_id", "kind", "direction"} <= interface.keys()
        assert_local_frame(interface, f"{spec['device_spec_id']}.{interface['interface_id']}")

    for port in process_ports:
        assert {"port_id", "direction", "role"} <= port.keys()
        if port.get("bound_physical_interface"):
            assert port["bound_physical_interface"] in physical_ids
        for signal_id in port.get("bound_signal_ports", []):
            assert signal_id in signal_ids
        if "local_frame" in port:
            assert_local_frame(port, f"{spec['device_spec_id']}.{port['port_id']}")

    for signal in signal_ports:
        assert {"port_id", "direction", "value_type"} <= signal.keys()
        bound_to = signal.get("bound_to")
        if not bound_to:
            continue
        assert isinstance(bound_to, dict)
        if bound_to.get("type") == "process_port":
            assert bound_to.get("id") in process_ids
        if bound_to.get("type") == "physical_interface":
            assert bound_to.get("id") in physical_ids

    for binding in bindings:
        assert binding.get("binding_id")
        if binding.get("physical_interface"):
            assert binding["physical_interface"] in physical_ids
        if binding.get("process_port"):
            assert binding["process_port"] in process_ids
        for signal_id in binding.get("signal_ports", []):
            assert signal_id in signal_ids
        for behavior_id in binding.get("transport_behaviors", []):
            assert behavior_id in behavior_ids

    for behavior in behaviors:
        for key in ["input_physical_interface", "output_physical_interface"]:
            if behavior.get(key):
                assert behavior[key] in physical_ids
        for key in ["input_process_port", "output_process_port"]:
            if behavior.get(key):
                assert behavior[key] in process_ids
        for key in ["input_signals", "output_signals", "control_signals"]:
            for signal_id in behavior.get(key, []):
                assert signal_id in signal_ids


def endpoint_port(scene: dict[str, Any], specs: dict[str, dict[str, Any]], endpoint: str, section: str) -> dict[str, Any]:
    instance_id, port_id = endpoint.split(".", 1)
    instance = next(item for item in scene["instances"] if item["instance_id"] == instance_id)
    spec = specs[instance["spec_id"]]
    key = "interface_id" if section == "physical_interfaces" else "port_id"
    return next(item for item in spec[section] if item[key] == port_id)


def assert_scene_contract(scene: dict[str, Any], specs: dict[str, dict[str, Any]]) -> None:
    for section in ["scene_id", "revision", "instances", "materials", "process_edges", "physical_edges", "signal_edges", "runtime_config"]:
        assert section in scene

    assert_unique(ids(scene["instances"], "instance_id"), "instances")
    assert all(instance["spec_id"] in specs for instance in scene["instances"])

    edge_ids = {section: set(ids(scene[section], "edge_id")) for section in ["process_edges", "physical_edges", "signal_edges"]}

    for edge in scene["process_edges"]:
        source = endpoint_port(scene, specs, edge["source"], "process_ports")
        target = endpoint_port(scene, specs, edge["target"], "process_ports")
        assert source["direction"] in {"output", "bidirectional", "internal"}
        assert target["direction"] in {"input", "bidirectional", "internal"}
        assert set(edge.get("compiled_physical_edges", [])) <= edge_ids["physical_edges"]
        assert set(edge.get("compiled_signal_edges", [])) <= edge_ids["signal_edges"]

    for edge in scene["physical_edges"]:
        source = endpoint_port(scene, specs, edge["source"], "physical_interfaces")
        target = endpoint_port(scene, specs, edge["target"], "physical_interfaces")
        assert source["direction"] in {"output", "bidirectional", "none"}
        assert target["direction"] in {"input", "bidirectional", "none"}
        if edge.get("compiled_from"):
            assert edge["compiled_from"] in edge_ids["process_edges"]

    for edge in scene["signal_edges"]:
        source = endpoint_port(scene, specs, edge["source"], "signal_ports")
        target = endpoint_port(scene, specs, edge["target"], "signal_ports")
        assert source["direction"] in {"output", "bidirectional"}
        assert target["direction"] in {"input", "bidirectional"}


def default_device_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted((SIM_SCHEMA_ROOT / "1.DeviceSpec").glob("*/*_1.json")):
        spec = read_json(path)
        specs[spec["device_spec_id"]] = spec
    return specs


def test_default_device_specs_keep_vc_aligned_interface_layers() -> None:
    specs = default_device_specs()
    assert len(specs) == 8
    for spec in specs.values():
        assert_device_spec_contract(spec)


def test_scene_and_demo_edges_resolve_to_typed_ports() -> None:
    specs = default_device_specs()
    scene = read_json(SIM_SCHEMA_ROOT / "2.SceneDocument" / "example.json")
    assert_scene_contract(scene, specs)

    full_chain = read_json(SIM_SCHEMA_ROOT / "demo" / "pallet_sorting_line" / "full_chain_schema.json")
    demo_specs = full_chain["device_specs"]
    for spec in demo_specs.values():
        assert_device_spec_contract(spec)
    assert_scene_contract(full_chain["scene_document"], demo_specs)

    topology = full_chain["topology_graph"]
    assert topology["source_scene"]["scene_id"] == full_chain["scene_document"]["scene_id"]
    assert topology["source_scene"]["scene_revision"] == full_chain["scene_document"]["revision"]
    for graph_key, scene_key in [("process_graph", "process_edges"), ("physical_graph", "physical_edges"), ("signal_graph", "signal_edges")]:
        topology_sources = {edge.get("source_scene_edge") or edge["edge_id"] for edge in topology[graph_key]["edges"]}
        scene_sources = {edge["edge_id"] for edge in full_chain["scene_document"][scene_key]}
        assert scene_sources <= topology_sources
