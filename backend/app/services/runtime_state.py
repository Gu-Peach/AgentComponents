from __future__ import annotations

import json
from typing import Any, Protocol

import redis

from app.core.config import settings


class RuntimeStateStore(Protocol):
    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None: ...
    def get_snapshot(self, run_id: str) -> dict[str, Any] | None: ...
    def set_signal(
        self,
        run_id: str,
        signal_id: str,
        value: Any,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
        *,
        event_type: str = "signal_event",
        event_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
    def get_signals(self, run_id: str) -> dict[str, Any]: ...
    def append_event(self, run_id: str, event: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]: ...
    def get_events(self, run_id: str) -> list[dict[str, Any]]: ...
    def enqueue_device_task(self, run_id: str, task: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]: ...
    def get_device_tasks(self, run_id: str) -> list[dict[str, Any]]: ...
    def clear_run(self, run_id: str) -> None: ...


class RedisRuntimeStateStore:
    # 初始化 Redis 客户端：根据 redis_url 创建连接，并让 Redis 返回字符串结果。
    def __init__(self, redis_url: str = settings.redis_url) -> None:
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    # 写入运行时快照：把指定 run_id 的 snapshot 序列化后存入 Redis，并设置过期时间。
    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None:
        ttl = ttl_seconds or settings.runtime_state_ttl_seconds
        self.client.set(self._snapshot_key(run_id), json.dumps(snapshot), ex=ttl)

    # 获取运行时快照：从 Redis 读取指定 run_id 的 snapshot，并反序列化为字典。
    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        raw = self.client.get(self._snapshot_key(run_id))
        return json.loads(raw) if raw else None

    # 设置信号状态：保存指定 signal_id 的最新事件，同时写入事件流用于后续消费。
    def set_signal(
        self,
        run_id: str,
        signal_id: str,
        value: Any,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
        *,
        event_type: str = "signal_event",
        event_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {"signal_id": signal_id, "value": value, "payload": payload, **(event_metadata or {})}
        self.client.hset(self._signals_key(run_id), signal_id, json.dumps(event))
        self.client.expire(self._signals_key(run_id), ttl_seconds or settings.runtime_state_ttl_seconds)
        self.append_event(run_id, {"type": event_type, **event}, ttl_seconds)
        return event

    # 获取所有信号状态：读取指定 run_id 下已保存的全部信号事件。
    def get_signals(self, run_id: str) -> dict[str, Any]:
        return {key: json.loads(value) for key, value in self.client.hgetall(self._signals_key(run_id)).items()}

    def append_event(self, run_id: str, event: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        self.client.xadd(self._stream_key(run_id), {"event": json.dumps(event)})
        self.client.expire(self._stream_key(run_id), ttl_seconds or settings.runtime_state_ttl_seconds)
        return event

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for stream_id, fields in self.client.xrange(self._stream_key(run_id), "-", "+"):
            event = json.loads(fields["event"])
            events.append({"stream_id": stream_id, **event})
        return events

    def enqueue_device_task(self, run_id: str, task: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        self.client.xadd(self._device_tasks_key(run_id), {"task": json.dumps(task)})
        self.client.expire(self._device_tasks_key(run_id), ttl_seconds or settings.runtime_state_ttl_seconds)
        return task

    def get_device_tasks(self, run_id: str) -> list[dict[str, Any]]:
        tasks: list[dict[str, Any]] = []
        for stream_id, fields in self.client.xrange(self._device_tasks_key(run_id), "-", "+"):
            task = json.loads(fields["task"])
            tasks.append({"stream_id": stream_id, **task})
        return tasks

    # 清空运行数据：删除指定 run_id 对应的快照、信号状态和事件流。
    def clear_run(self, run_id: str) -> None:
        self.client.delete(self._snapshot_key(run_id), self._signals_key(run_id), self._stream_key(run_id), self._device_tasks_key(run_id))

    # 生成快照存储键：统一 Redis 中 snapshot 的 key 命名。
    @staticmethod
    def _snapshot_key(run_id: str) -> str:
        return f"runtime:simulation:{run_id}:snapshot"

    # 生成信号存储键：统一 Redis 中 signals 哈希表的 key 命名。
    @staticmethod
    def _signals_key(run_id: str) -> str:
        return f"runtime:simulation:{run_id}:signals"

    # 生成事件流存储键：统一 Redis 中 simulation events stream 的 key 命名。
    @staticmethod
    def _stream_key(run_id: str) -> str:
        return f"stream:simulation:{run_id}:events"

    @staticmethod
    def _device_tasks_key(run_id: str) -> str:
        return f"runtime:simulation:{run_id}:device_tasks"


class InMemoryRuntimeStateStore:
    # 初始化内存存储：用 Python 字典临时保存快照和信号状态。
    def __init__(self) -> None:
        self.snapshots: dict[str, dict[str, Any]] = {}
        self.signals: dict[str, dict[str, Any]] = {}
        self.events: dict[str, list[dict[str, Any]]] = {}
        self.device_tasks: dict[str, list[dict[str, Any]]] = {}

    # 写入运行时快照：把指定 run_id 的 snapshot 保存到内存字典。
    def put_snapshot(self, run_id: str, snapshot: dict[str, Any], ttl_seconds: int | None = None) -> None:
        self.snapshots[run_id] = snapshot

    # 获取运行时快照：从内存字典读取指定 run_id 的 snapshot。
    def get_snapshot(self, run_id: str) -> dict[str, Any] | None:
        return self.snapshots.get(run_id)

    # 设置信号状态：把指定 signal_id 的最新事件保存到内存字典。
    def set_signal(
        self,
        run_id: str,
        signal_id: str,
        value: Any,
        payload: dict[str, Any],
        ttl_seconds: int | None = None,
        *,
        event_type: str = "signal_event",
        event_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {"signal_id": signal_id, "value": value, "payload": payload, **(event_metadata or {})}
        self.signals.setdefault(run_id, {})[signal_id] = event
        self.append_event(run_id, {"type": event_type, **event}, ttl_seconds)
        return event

    # 获取所有信号状态：返回指定 run_id 下已保存的全部信号事件。
    def get_signals(self, run_id: str) -> dict[str, Any]:
        return self.signals.get(run_id, {})

    def append_event(self, run_id: str, event: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        self.events.setdefault(run_id, []).append(event)
        return event

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        return self.events.get(run_id, [])

    def enqueue_device_task(self, run_id: str, task: dict[str, Any], ttl_seconds: int | None = None) -> dict[str, Any]:
        self.device_tasks.setdefault(run_id, []).append(task)
        return task

    def get_device_tasks(self, run_id: str) -> list[dict[str, Any]]:
        return self.device_tasks.get(run_id, [])

    # 清空运行数据：从内存中删除指定 run_id 的快照和信号状态。
    def clear_run(self, run_id: str) -> None:
        self.snapshots.pop(run_id, None)
        self.signals.pop(run_id, None)
        self.events.pop(run_id, None)
        self.device_tasks.pop(run_id, None)
