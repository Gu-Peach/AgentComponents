"""Tool node helper for reading SceneDocument inputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..utils.json_io import read_json


class SceneReader:
    """Read SceneDocument files and normalize the facts needed by the agent."""

    def read(self, scene_document_ref: str | Path) -> dict[str, Any]:
        raw = read_json(scene_document_ref)
        scene_doc = raw.get("scene_document", raw)
        instances = scene_doc.get("instances", [])
        materials = scene_doc.get("materials", [])
        spec_refs = sorted({instance.get("spec_id") for instance in instances if instance.get("spec_id")})
        return {
            "raw": scene_doc,
            "scene_id": scene_doc.get("scene_id", raw.get("scene_id", "unknown_scene")),
            "scene_revision": scene_doc.get("revision", scene_doc.get("scene_revision", raw.get("revision", "unknown_revision"))),
            "instances": instances,
            "materials": materials,
            "physical_edges": scene_doc.get("physical_edges", []),
            "process_edges": scene_doc.get("process_edges", []),
            "signal_edges": scene_doc.get("signal_edges", []),
            "device_spec_refs": spec_refs,
            "instance_index": {instance.get("instance_id"): instance for instance in instances if instance.get("instance_id")},
            "material_index": {material.get("material_id"): material for material in materials if material.get("material_id")},
        }
