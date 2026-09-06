from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///./.test_backend.db")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")

DB_FILE = Path(".test_backend.db")
if DB_FILE.exists():
    DB_FILE.unlink()

from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.dependencies import get_runtime_store  # noqa: E402
from app.main import app  # noqa: E402
from app.services.runtime_state import InMemoryRuntimeStateStore  # noqa: E402


def pytest_configure() -> None:
    Base.metadata.create_all(bind=engine)


def pytest_runtest_setup() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_runtime_store] = lambda: InMemoryRuntimeStateStore()


def pytest_runtest_teardown() -> None:
    app.dependency_overrides.clear()


def make_client() -> TestClient:
    return TestClient(app)
