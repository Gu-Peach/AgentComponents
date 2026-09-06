from __future__ import annotations

from functools import lru_cache

from app.services.runtime_state import RedisRuntimeStateStore, RuntimeStateStore


@lru_cache(maxsize=1)
def get_runtime_store() -> RuntimeStateStore:
    return RedisRuntimeStateStore()

