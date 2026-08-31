"""Configuration for the SceneBehaviorGraph agent."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AgentConfig:
    repo_root: Path
    max_repair_attempts: int = 2
    auto_approve: bool = True

    @property
    def simulation_schema_root(self) -> Path:
        return self.repo_root / "docs" / "business" / "SimulationSchema"

    @property
    def default_output_dir(self) -> Path:
        return self.repo_root / "agent" / "scene_behavior_agent" / "examples" / "output"


def default_config() -> AgentConfig:
    return AgentConfig(repo_root=Path(__file__).resolve().parents[3])
