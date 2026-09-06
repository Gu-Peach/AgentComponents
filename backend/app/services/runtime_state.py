from __future__ import annotations

import json
from typing import Any, Protocol

import redis

from app.core.config import settings


class RuntimeStateStore(Protocol):
    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None: ...
    def get_snapshot(self, run_id: str) -> dict[str, Any] | None: ...
    def set_signal(self, run_id: str, signal_id: str, value: Any, payload: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]: ...
    def get_signals(self, run_id: str) -> dict[str, Any]: ...
    def clear_run(self, run_id: str) -> None: ...


class RedisRuntimeStateStore:
    def __init__(self, redis_url: str = settings.redis_url) -> None:
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or settings.runtime_state_ttl_seconds
        self.client.set(self._snapshot_key(run_id), json.dumps(snapshot), ex=ttl)

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self._snapshot_key(run_id))
        return json.loads(raw) if raw else None

    def set_signal(self, run_id: str, signal_id: str, value: Any, payload: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        event = {"signal_id": signal_id, "value": value, "payload": payload}
        self.client.hset(self._signals_key(run_id), signal_id, json.dumps(event))
        self.client.expire(self._signals_key(run_id), ttl_seconds or settings.runtime_state_ttl_seconds)
        self.client.xadd(self._stream_key(run_id), {"event": json.dumps({"type": "signal_event", **event})})
        return event

    def get_signals(self, run_id: str) -> dict[str, Any]:
        return {key: json.loads(value) for key, value in self.client.hgetall(self._signals_key(run_id)).items()}

    def clear_run(self, run_id: str) -> None:
        self.client.delete(self._snapshot_key(run_id), self._signals_key(run_id), self._stream_key(run_id))

    @staticmethod
    def _snapshot_key(run_id: str) -> str:
        return f"runtime:simulation:{run_id}:snapshot"

    @staticmethod
    def _signals_key(run_id: str) -> str:
        return f"runtime:simulation:{run_id}:signals"

    @staticmethod
    def _stream_key(run_id: str) -> str:
        return f"stream:simulation:{run_id}:events"


class InMemoryRuntimeStateStore:
    def __init__(self) -> None:
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.signals: dict[str, dict[str, Any]] = {}

    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None:
        self.snapshots[run_id] = snapshot

    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        return self.snapshots.get(run_id)

    def set_signal(self, run_id: str, signal_id: str, value: Any, payload: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        event = {"signal_id": signal_id, "value": value, "payload": payload}
        self.signals.setdefault(run_id, {})[signal_id] = event
        return event

    def get_signals(self, run_id: str) -> dict[str, Any]:
        return self.signals.get(run_id, {})

    def clear_run(self, run_id: str) -> None:
        self.snapshots.pop(run_id, None)
        self.signals.pop(run_id, None)

