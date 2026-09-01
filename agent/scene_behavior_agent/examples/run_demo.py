"""Run the SceneBehaviorGraph agent against the pallet sorting demo."""

from __future__ import annotations

from pathlib import Path

from agent.scene_behavior_agent.graph.runner import invoke_agent
from agent.scene_behavior_agent.schemas.config import default_config


def main() -> None:
    config = default_config()
    scene_path = config.simulation_schema_root / "2.SceneDocument" / "example.json"
    output_path = config.default_output_dir / "scene_behavior_graph.generated.json"
    state = invoke_agent(
        {
            "scene_document_ref": str(scene_path),
            "user_goal_raw": "托盘经两段主传送带到达分拣位，然后两台机械臂持续分拣 12 个工件到上下出料传送带；所有传送带都按停留点占用推进，出料传送带满载时暂停对应机械臂并在容量恢复后继续。",
            "output_path": str(output_path),
        },
        config=config,
    )
    print(state.get("explanation", ""))
    print(f"Generated: {Path(state.get('output_path', output_path)).resolve()}")


if __name__ == "__main__":
    main()
