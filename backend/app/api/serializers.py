from __future__ import annotations

from app.db import models


def project_response(project: models.Project) -> dict:
    return {"id": project.id, "name": project.name, "description": project.description}


def asset_response(asset: models.Asset) -> dict:
    return {
        "asset_id": asset.id,
        "bucket": asset.bucket,
        "path": asset.path,
        "provider": asset.provider,
        "mime_type": asset.mime_type,
        "size_bytes": asset.size_bytes,
        "metadata": asset.metadata_json,
    }


def device_spec_response(spec: models.DeviceSpec) -> dict:
    return {
        "spec_id": spec.id,
        "spec_key": spec.spec_key,
        "device_type": spec.device_type,
        "version": spec.version,
        "display_name": spec.display_name,
        "document": spec.document,
    }


def scene_response(scene: models.Scene) -> dict:
    return {"scene_id": scene.id, "project_id": scene.project_id, "revision": scene.revision, "document": scene.current_document}


def simulation_run_response(run: models.SimulationRun) -> dict:
    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "scene_id": run.scene_id,
        "base_scene_revision": run.base_scene_revision,
        "status": run.status,
        "runtime_snapshot": run.runtime_snapshot,
    }

