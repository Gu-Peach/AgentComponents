"""Simple long-term pattern memory for reusable modeling templates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InMemoryPatternStore:
    """Minimal store abstraction for reusable SceneBehaviorGraph patterns."""

    patterns: dict[str, dict[str, Any]] = field(default_factory=dict)

    def put(self, key: str, value: dict[str, Any]) -> None:
        self.patterns[key] = value

    def get(self, key: str) -> dict[str, Any] | None:
        return self.patterns.get(key)

    def search(self, keyword: str) -> list[dict[str, Any]]:
        return [value for key, value in self.patterns.items() if keyword.lower() in key.lower()]
