from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


class NotFoundError(AppError):
    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__("NOT_FOUND", f"{resource} not found: {resource_id}", 404, {"resource_id": resource_id})


class RevisionConflictError(AppError):
    def __init__(self, expected_revision: int, current_revision: int) -> None:
        super().__init__(
            "SCENE_REVISION_CONFLICT",
            "Scene changed after this request was prepared.",
            409,
            {"expected_revision": expected_revision, "current_revision": current_revision},
        )

