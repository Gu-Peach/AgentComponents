"""Tool node helper for loading DeviceSpec documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..schemas.config import AgentConfig
from ..utils.json_io import read_json


class DeviceSpecReader:
    """Resolve and read DeviceSpec files from SimulationSchema."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.device_spec_root = config.simulation_schema_root / "1.DeviceSpec"

    def read_many(self, spec_ids: list[str]) -> dict[str, Any]:
        specs: dict[str, Any] = {}
        missing: list[str] = []
        for spec_id in spec_ids:
            path = self._resolve_spec_path(spec_id)
            if not path:
                missing.append(spec_id)
                continue
            spec = read_json(path)
            normalized_id = spec.get("device_spec_id") or spec.get("id") or spec_id
            specs[normalized_id] = spec
        return {
            "specs": specs,
            "missing": missing,
            "behavior_index": self._build_behavior_index(specs),
            "signal_port_index": self._build_signal_port_index(specs),
            "resource_index": self._build_resource_index(specs),
            "capacity_index": self._build_capacity_index(specs),
            "stop_point_model_index": self._build_stop_point_model_index(specs),
            "summary": self._build_summary(specs, missing),
        }

    def _resolve_spec_path(self, spec_id: str) -> Path | None:
        candidates = list(self.device_spec_root.glob(f"**/{spec_id}.json"))
        if candidates:
            return candidates[0]
        for path in self.device_spec_root.glob("**/*.json"):
            if path.name in {"schema.json", "template.json", "common_device_spec.schema.json", "example.json"}:
                continue
            try:
                data = read_json(path)
            except Exception:
                continue
            if data.get("device_spec_id") == spec_id or data.get("id") == spec_id:
                return path
        return None

    @staticmethod
    def _build_behavior_index(specs: dict[str, Any]) -> dict[str, list[str]]:
        return {
            spec_id: [behavior.get("behavior_id") for behavior in spec.get("transport_behaviors", []) if behavior.get("behavior_id")]
            for spec_id, spec in specs.items()
        }

    @staticmethod
    def _build_signal_port_index(specs: dict[str, Any]) -> dict[str, list[str]]:
        return {
            spec_id: [port.get("port_id") for port in spec.get("signal_ports", []) if port.get("port_id")]
            for spec_id, spec in specs.items()
        }

    @staticmethod
    def _build_resource_index(specs: dict[str, Any]) -> dict[str, list[str]]:
        resource_index: dict[str, list[str]] = {}
        for spec_id, spec in specs.items():
            resources = []
            for resource in spec.get("runtime_contract", {}).get("resources", []):
                if resource.get("resource_id"):
                    resources.append(resource["resource_id"])
            for behavior in spec.get("transport_behaviors", []):
                resources.extend(behavior.get("resources", []))
            resource_index[spec_id] = sorted(set(resources))
        return resource_index

    @staticmethod
    def _build_capacity_index(specs: dict[str, Any]) -> dict[str, Any]:
        return {
            spec_id: spec.get("runtime_contract", {}).get("capacity", {})
            for spec_id, spec in specs.items()
        }

    @staticmethod
    def _build_stop_point_model_index(specs: dict[str, Any]) -> dict[str, Any]:
        return {
            spec_id: spec.get("type_specific_contract", {}).get("stop_point_model")
            for spec_id, spec in specs.items()
            if spec.get("type_specific_contract", {}).get("stop_point_model")
        }

    @staticmethod
    def _build_summary(specs: dict[str, Any], missing: list[str]) -> dict[str, Any]:
        devices = []
        for spec_id, spec in specs.items():
            devices.append(
                {
                    "spec_id": spec_id,
                    "device_type": spec.get("device_type"),
                    "behaviors": [behavior.get("behavior_id") for behavior in spec.get("transport_behaviors", [])],
                    "signals": [port.get("port_id") for port in spec.get("signal_ports", [])],
                    "default_state": spec.get("runtime_contract", {}).get("default_state"),
                    "capacity": spec.get("runtime_contract", {}).get("capacity", {}),
                    "stop_point_model": spec.get("type_specific_contract", {}).get("stop_point_model"),
                }
            )
        return {"devices": devices, "missing": missing}
