"""SceneBehaviorGraph generation agent.

The package follows the LangGraph design in docs/design/agent_design.md.
Runtime scheduling is intentionally out of scope: this package generates the
SceneBehaviorGraph consumed by Runtime/Scheduler.
"""

from .schemas.state import AgentState

__all__ = ["AgentState"]
