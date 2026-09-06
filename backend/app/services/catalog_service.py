from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.db import models
from app.repositories.sql import AssetRepository, DeviceSpecRepository
from app.schemas.domain import AssetCreate, DeviceSpecCreate
from app.services.ids import new_id


DEFAULT_DEVICE_SPEC_FILES = [
    "docs/business/SimulationSchema/1.DeviceSpec/conveyor/conveyor_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/robot_arm/robot_arm_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/workpiece/workpiece_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/workpiece_carrier/carrier_tray_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/lift_table/lift_table_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/material_source_station/material_source_station_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/rotary_table/rotary_table_1.json",
    "docs/business/SimulationSchema/1.DeviceSpec/storage_rack/storage_rack_1.json",
]


class DeviceSpecService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DeviceSpecRepository(db)

    def create_or_update(self, payload: DeviceSpecCreate) -> models.DeviceSpec:
        document = payload.document
        spec_id = payload.spec_id or document.get("device_spec_id") or document.get("schema_id")
        if not spec_id:
            raise AppError("INVALID_DEVICE_SPEC", "DeviceSpec document must include device_spec_id or schema_id.")
        device_type = document.get("device_type")
        if not device_type:
            raise AppError("INVALID_DEVICE_SPEC", "DeviceSpec document must include device_type.")
        spec_key = payload.spec_key or spec_id
        spec = models.DeviceSpec(
            id=spec_id,
            spec_key=spec_key,
            device_type=device_type,
            version=document.get("version", "0.2.0"),
            display_name=document.get("display_name") or document.get("name") or spec_id,
            document=document,
        )
        saved = self.repo.upsert(spec)
        self.db.commit()
        self.db.refresh(saved)
        return saved

    def import_defaults(self) -> list[models.DeviceSpec]:
        repo_root = Path(__file__).resolve().parents[3]
        imported: list[models.DeviceSpec] = []
        for relative in DEFAULT_DEVICE_SPEC_FILES:
            file = repo_root / relative
            if not file.exists():
                continue
            document = json.loads(file.read_text(encoding="utf-8-sig"))
            spec_id = document.get("device_spec_id") or document.get("schema_id")
            imported.append(
                self.repo.upsert(
                    models.DeviceSpec(
                        id=spec_id,
                        spec_key=spec_id,
                        device_type=document["device_type"],
                        version=document.get("version", "0.2.0"),
                        display_name=document.get("display_name") or document.get("name") or spec_id,
                        document=document,
                    )
                )
            )
        self.db.commit()
        return imported

    def list(self, device_type: str | None = None) -> list[models.DeviceSpec]:
        return self.repo.list(device_type)

    def get(self, spec_id: str) -> models.DeviceSpec:
        spec = self.repo.get(spec_id) or self.repo.get_by_key(spec_id)
        if not spec:
            raise NotFoundError("DeviceSpec", spec_id)
        return spec


class AssetService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AssetRepository(db)

    def create(self, payload: AssetCreate) -> models.Asset:
        asset = models.Asset(
            id=new_id("asset"),
            bucket=payload.bucket,
            path=payload.path,
            provider=payload.provider,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            metadata_json=payload.metadata,
        )
        self.repo.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def list(self) -> list[models.Asset]:
        return self.repo.list()

    def get(self, asset_id: str) -> models.Asset:
        asset = self.repo.get(asset_id)
        if not asset:
            raise NotFoundError("Asset", asset_id)
        return asset

