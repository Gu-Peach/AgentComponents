from __future__ import annotations

import json
from pathlib import Path

from app.services.interface_compiler import InterfaceCompiler
from app.services.topology_builder import TopologyBuilder
from app.services.validation import build_scene_context, validate_physical_edge


def read_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def test_compiler_uses_bindings_without_merging_interface_types() -> None:
    conveyor = read_json("../docs/business/SimulationSchema/1.DeviceSpec/conveyor/conveyor_1.json")
    robot = read_json("../docs/business/SimulationSchema/1.DeviceSpec/robot_arm/robot_arm_1.json")
    scene = {
        "scene_id": "scene_test",
        "revision": 7,
        "instances": [
            {"instance_id": "conveyor_1", "spec_id": "conveyor_1", "device_type": "conveyor"},
            {"instance_id": "robot_1", "spec_id": "robot_arm_1", "device_type": "robot_arm"},
        ],
        "process_edges": [{"edge_id": "proc_1", "source": "conveyor_1.flow_output", "target": "robot_1.flow_input", "edge_type": "material_flow"}],
        "physical_edges": [],
        "signal_edges": [],
        "materials": [],
    }

    result = InterfaceCompiler().compile(scene, {"conveyor_1": conveyor, "robot_arm_1": robot})

    assert result["compiled_physical_edges"] == [
        {
            "edge_id": "phys_proc_1",
            "source": "conveyor_1.exit",
            "target": "robot_1.pick_area",
            "edge_type": "physical_connection",
            "connection_method": "compiled_from_process",
            "compiled_from": "proc_1",
            "is_inferred": True,
            "confidence": 0.8,
            "compatibility_result": {"status": "not_checked", "matched_fields": [], "missing_fields": []},
            "snap_result": {"distance_m": None, "angle_deg": None, "within_tolerance": "not_checked", "retain_offset": False},
        }
    ]
    signal_targets = {edge["target"] for edge in result["compiled_signal_edges"]}
    assert "robot_1.start_pick" in signal_targets
    assert "robot_1.pause_pick" in signal_targets
    assert all(edge["source"].startswith("conveyor_1.") for edge in result["compiled_signal_edges"])


def test_compiler_keeps_process_ports_as_material_flow_points_without_physical_binding() -> None:
    conveyor = {
        "device_spec_id": "conveyor_spec",
        "physical_interfaces": [
            {"interface_id": "bbox_bottom_front_left", "kind": "layout_mount_anchor", "direction": "none"},
            {"interface_id": "bbox_bottom_front_right", "kind": "layout_mount_anchor", "direction": "none"},
        ],
        "process_ports": [
            {"port_id": "flow_output", "direction": "output", "role": "flow_output", "bound_signal_ports": ["part_ready"]},
        ],
        "signal_ports": [
            {"port_id": "part_ready", "direction": "output", "value_type": "event"},
        ],
        "interface_bindings": [
            {"binding_id": "bind_flow_output", "process_port": "flow_output", "signal_ports": ["part_ready"]},
        ],
    }
    robot = {
        "device_spec_id": "robot_spec",
        "physical_interfaces": [
            {"interface_id": "bbox_bottom_front_left", "kind": "layout_mount_anchor", "direction": "none"},
            {"interface_id": "bbox_bottom_front_right", "kind": "layout_mount_anchor", "direction": "none"},
        ],
        "process_ports": [
            {"port_id": "flow_input", "direction": "input", "role": "flow_input", "bound_signal_ports": ["start_pick"]},
        ],
        "signal_ports": [
            {"port_id": "start_pick", "direction": "input", "value_type": "event"},
        ],
        "interface_bindings": [
            {"binding_id": "bind_flow_input", "process_port": "flow_input", "signal_ports": ["start_pick"]},
        ],
    }
    scene = {
        "scene_id": "scene_process_points",
        "revision": 1,
        "instances": [
            {"instance_id": "conveyor_1", "spec_id": "conveyor_spec", "device_type": "conveyor"},
            {"instance_id": "robot_1", "spec_id": "robot_spec", "device_type": "robot_arm"},
        ],
        "process_edges": [{"edge_id": "proc_1", "source": "conveyor_1.flow_output", "target": "robot_1.flow_input", "edge_type": "material_flow"}],
        "physical_edges": [],
        "signal_edges": [],
    }

    result = InterfaceCompiler().compile(scene, {"conveyor_spec": conveyor, "robot_spec": robot})

    assert result["compiled_physical_edges"] == []
    assert result["compiled_signal_edges"] == [
        {
            "edge_id": "sig_proc_1_part_ready_to_start_pick",
            "source": "conveyor_1.part_ready",
            "target": "robot_1.start_pick",
            "edge_type": "control_signal",
            "delivery": "event",
            "trigger": "on_rising_edge",
            "transform": {"type": "identity"},
            "timeout_ms": 30000,
            "on_timeout": "raise_observation",
            "enabled": True,
            "compiled_from": "proc_1",
            "route_id": "route_sig_proc_1_part_ready_to_start_pick",
        }
    ]
    assert all(".None" not in edge.get("source", "") + edge.get("target", "") for edge in result["compiled_physical_edges"])
    assert result["warnings"] == [
        {
            "severity": "warning",
            "code": "PROCESS_EDGE_HAS_NO_PHYSICAL_BINDING",
            "message": "Process edge has no explicit physical-interface binding; only signal routing will be compiled.",
            "process_edge_id": "proc_1",
        }
    ]


def test_physical_edges_accept_layout_mount_anchors_with_none_direction() -> None:
    spec = {
        "device_spec_id": "fixture_spec",
        "physical_interfaces": [
            {"interface_id": "bbox_bottom_front_left", "kind": "layout_mount_anchor", "direction": "none"},
            {"interface_id": "bbox_bottom_front_right", "kind": "layout_mount_anchor", "direction": "none"},
        ],
    }
    scene = {
        "instances": [
            {"instance_id": "a", "spec_id": "fixture_spec"},
            {"instance_id": "b", "spec_id": "fixture_spec"},
        ]
    }
    ctx = build_scene_context(scene, {"fixture_spec": spec})

    assert validate_physical_edge(ctx, "a.bbox_bottom_front_left", "b.bbox_bottom_front_right") == []


def test_topology_builder_keeps_four_graphs_separate() -> None:
    scene = read_json("../docs/business/SimulationSchema/2.SceneDocument/example.json")
    specs = {
        "conveyor_1": read_json("../docs/business/SimulationSchema/1.DeviceSpec/conveyor/conveyor_1.json"),
        "robot_arm_1": read_json("../docs/business/SimulationSchema/1.DeviceSpec/robot_arm/robot_arm_1.json"),
        "carrier_tray_1": read_json("../docs/business/SimulationSchema/1.DeviceSpec/workpiece_carrier/carrier_tray_1.json"),
    }

    graph = TopologyBuilder().build(scene, specs)

    assert graph["physical_graph"]["edges"]
    assert graph["process_graph"]["edges"]
    assert graph["signal_graph"]["edges"]
    assert graph["transport_graph"]["links"]
    assert TopologyBuilder().is_reachable(graph, "main_conveyor_1.flow_output", "main_conveyor_2.flow_input") is True
