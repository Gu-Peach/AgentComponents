from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.serializers import device_spec_response
from app.db.session import get_db
from app.schemas.domain import DeviceSpecCreate, DeviceSpecResponse
from app.services.catalog_service import DeviceSpecService

router = APIRouter(prefix="/api/device-specs", tags=["device-specs"])


@router.post("", response_model=DeviceSpecResponse)
def create_device_spec(payload: DeviceSpecCreate, db: Session = Depends(get_db)) -> dict:
    return device_spec_response(DeviceSpecService(db).create_or_update(payload))


@router.post("/import-defaults", response_model=list[DeviceSpecResponse])
def import_default_device_specs(db: Session = Depends(get_db)) -> list[dict]:
    return [device_spec_response(spec) for spec in DeviceSpecService(db).import_defaults()]


@router.get("", response_model=list[DeviceSpecResponse])
def list_device_specs(device_type: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return [device_spec_response(spec) for spec in DeviceSpecService(db).list(device_type)]


@router.get("/{spec_id}", response_model=DeviceSpecResponse)
def get_device_spec(spec_id: str, db: Session = Depends(get_db)) -> dict:
    return device_spec_response(DeviceSpecService(db).get(spec_id))

