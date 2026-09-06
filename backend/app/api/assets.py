from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.serializers import asset_response
from app.db.session import get_db
from app.schemas.domain import AssetCreate, AssetResponse
from app.services.catalog_service import AssetService

router = APIRouter(prefix="/api/assets", tags=["assets"])


# 创建资产：POST /api/assets，接收资产信息并返回创建后的资产。
@router.post("", response_model=AssetResponse)
def create_asset(payload: AssetCreate, db: Session = Depends(get_db)) -> dict:
    return asset_response(AssetService(db).create(payload))


# 查询资产列表：GET /api/assets，返回所有资产。
@router.get("", response_model=list[AssetResponse])
def list_assets(db: Session = Depends(get_db)) -> list[dict]:
    return [asset_response(asset) for asset in AssetService(db).list()]


# 查询单个资产：GET /api/assets/{asset_id}，按 asset_id 返回资产详情。
@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(asset_id: str, db: Session = Depends(get_db)) -> dict:
    return asset_response(AssetService(db).get(asset_id))

