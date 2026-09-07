from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.serializers import project_response
from app.db.session import get_db
from app.schemas.domain import ProjectCreate, ProjectResponse
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


# 创建项目：POST /api/projects，接收项目名称和描述并返回创建后的项目。
@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> dict:
    return project_response(ProjectService(db).create(payload))


# 查询项目列表：GET /api/projects，返回所有项目。
@router.get("", response_model=list[ProjectResponse])
def list_projects(db: Session = Depends(get_db)) -> list[dict]:
    return [project_response(project) for project in ProjectService(db).list()]


# 查询单个项目：GET /api/projects/{project_id}，按 project_id 返回项目详情。
@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)) -> dict:
    return project_response(ProjectService(db).get(project_id))

