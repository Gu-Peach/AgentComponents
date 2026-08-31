"""LangGraph app export.

LangGraph CLI/Studio can load `graph` from this module using agent/langgraph.json.
If langgraph is not installed, importing this module raises a clear error; local
non-LangGraph execution remains available through graph.runner.
"""

from __future__ import annotations

from .builder import build_graph

try:
    graph = build_graph()
except ImportError as exc:  # pragma: no cover - optional runtime integration
    raise RuntimeError(
        "langgraph is required to load scene_behavior_agent.graph.app:graph. "
        "Install the optional dependency or use SequentialSceneBehaviorAgent."
    ) from exc
