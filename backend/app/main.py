from __future__ import annotations

from fastapi import FastAPI

from app.api import agent, assets, device_specs, projects, scenes, simulation
from app.core.config import settings
from app.core.errors import AppError, app_error_handler
from app.db.base import Base
from app.db.session import engine

# Register models with SQLAlchemy metadata.
import app.db.models  # noqa: F401


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_exception_handler(AppError, app_error_handler)

    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)

    app.include_router(projects.router)
    app.include_router(device_specs.router)
    app.include_router(assets.router)
    app.include_router(scenes.router)
    app.include_router(simulation.router)
    app.include_router(agent.router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": settings.app_name, "agent_enabled": True}

    return app


app = create_app()
