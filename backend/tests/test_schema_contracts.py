from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
SIM_SCHEMA_ROOT = REPO_ROOT / "docs" / "business" / "SimulationSchema"
FRONTEND_SCENE1_ROOT = REPO_ROOT / "frontend" / "public" / "test" / "scene1"


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
    assert_vector3(position, f"{label}.local_frame.position")
    assert local_frame.get("rotation_euler") is not None or local_frame.get("forward") is not None, f"{label} needs rotation_euler or forward"


def assert_vector3(value: Any, label: str) -> None:
    assert isinstance(value, list) and len(value) == 3, f"{label} must be [x, y, z]"
    assert all(isinstance(item, (int, float)) for item in value), f"{label} values must be numeric"


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
    for instance in scene["instances"]:
        assert_instance_runtime_contract(instance)

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


def assert_instance_runtime_contract(instance: dict[str, Any]) -> None:
    runtime_geometry = instance.get("runtime_geometry")
    if runtime_geometry:
        assert isinstance(runtime_geometry, dict), f"{instance['instance_id']}.runtime_geometry must be object"
        for port_id, point in runtime_geometry.get("process_points", {}).items():
            assert isinstance(point, dict), f"{instance['instance_id']}.{port_id} process point must be object"
            assert_vector3(point.get("position"), f"{instance['instance_id']}.runtime_geometry.process_points.{port_id}.position")

        for path_key in ["transport_path", "pick_place_path"]:
            path = runtime_geometry.get(path_key)
            if not path:
                continue
            assert isinstance(path, dict), f"{instance['instance_id']}.runtime_geometry.{path_key} must be object"
            for position_key in ["start_position", "end_position", "pick_position", "place_position"]:
                if path.get(position_key) is not None:
                    assert_vector3(path[position_key], f"{instance['instance_id']}.{path_key}.{position_key}")
            for index, waypoint in enumerate(path.get("waypoints", [])):
                assert_vector3(waypoint, f"{instance['instance_id']}.{path_key}.waypoints[{index}]")
            for point in path.get("stop_points", []):
                assert_vector3(point.get("position"), f"{instance['instance_id']}.{path_key}.{point.get('point_id')}.position")

    runtime_kinematics = instance.get("runtime_kinematics")
    if runtime_kinematics:
        assert isinstance(runtime_kinematics, dict), f"{instance['instance_id']}.runtime_kinematics must be object"
        chain = runtime_kinematics.get("kinematic_chain")
        assert isinstance(chain, dict), f"{instance['instance_id']}.runtime_kinematics.kinematic_chain must be object"
        joints = chain.get("joints", [])
        assert isinstance(joints, list) and joints, f"{instance['instance_id']}.runtime_kinematics.kinematic_chain.joints required"
        for joint in joints:
            assert joint.get("name") and joint.get("nodeName") and joint.get("type"), f"invalid runtime joint: {joint}"


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


def test_frontend_scene1_scene_document_has_runtime_instance_geometry() -> None:
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted((FRONTEND_SCENE1_ROOT / "device_specs").glob("*.json")):
        if path.name == "index.json":
            continue
        spec = read_json(path)
        assert_device_spec_contract(spec)
        specs[spec["device_spec_id"]] = spec

    scene = read_json(FRONTEND_SCENE1_ROOT / "scene_document.json")
    assert_scene_contract(scene, specs)

    robots = [instance for instance in scene["instances"] if instance["device_type"] == "robot_arm"]
    assert {robot["instance_id"] for robot in robots} == {"robot_1", "robot_2"}
    for robot in robots:
        assert robot["runtime_geometry"]["pick_place_path"]["waypoints"]
        assert robot["runtime_kinematics"]["kinematic_chain"]["joints"]
