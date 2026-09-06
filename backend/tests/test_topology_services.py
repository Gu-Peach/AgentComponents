from __future__ import annotations

import json
from pathlib import Path

from app.services.interface_compiler import InterfaceCompiler
from app.services.topology_builder import TopologyBuilder


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

