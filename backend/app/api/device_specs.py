from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.serializers import device_spec_response
from app.db.session import get_db
from app.schemas.domain import DeviceSpecCreate, DeviceSpecResponse
from app.services.catalog_service import DeviceSpecService

router = APIRouter(prefix="/api/device-specs", tags=["device-specs"])


# 新建或更新设备规格：POST /api/device-specs，接收设备规格文档并返回保存后的规格。
@router.post("", response_model=DeviceSpecResponse)
def create_device_spec(payload: DeviceSpecCreate, db: Session = Depends(get_db)) -> dict:
    return device_spec_response(DeviceSpecService(db).create_or_update(payload))


# 导入默认设备规格：POST /api/device-specs/import-defaults，返回导入后的规格列表。
@router.post("/import-defaults", response_model=list[DeviceSpecResponse])
def import_default_device_specs(db: Session = Depends(get_db)) -> list[dict]:
    return [device_spec_response(spec) for spec in DeviceSpecService(db).import_defaults()]


# 查询设备规格列表：GET /api/device-specs，可通过 device_type 查询参数按类型过滤。
@router.get("", response_model=list[DeviceSpecResponse])
def list_device_specs(device_type: str | None = Query(default=None), db: Session = Depends(get_db)) -> list[dict]:
    return [device_spec_response(spec) for spec in DeviceSpecService(db).list(device_type)]


# 查询单个设备规格：GET /api/device-specs/{spec_id}，按 spec_id 返回规格详情。
@router.get("/{spec_id}", response_model=DeviceSpecResponse)
def get_device_spec(spec_id: str, db: Session = Depends(get_db)) -> dict:
    return device_spec_response(DeviceSpecService(db).get(spec_id))

