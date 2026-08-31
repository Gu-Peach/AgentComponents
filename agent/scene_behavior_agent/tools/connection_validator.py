"""Explicit ConnectionValidator tool wrapper."""

from __future__ import annotations

from typing import Any

from .graph_validator import GraphValidator
from ..schemas.state import ValidationReport


class ConnectionValidator:
    """Validate explicit SceneDocument connections before behavior modeling."""

    def __init__(self) -> None:
        self._validator = GraphValidator()

    def validate(self, scene_facts: dict[str, Any], device_capabilities: dict[str, Any]) -> ValidationReport:
        return self._validator.validate_connections(scene_facts, device_capabilities)
