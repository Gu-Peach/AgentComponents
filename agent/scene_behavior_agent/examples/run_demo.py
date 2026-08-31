"""Run the SceneBehaviorGraph agent against the pallet sorting demo."""

from __future__ import annotations

from pathlib import Path

from agent.scene_behavior_agent.graph.runner import invoke_agent
from agent.scene_behavior_agent.schemas.config import default_config


def main() -> None:
    config = default_config()
    scene_path = config.simulation_schema_root / "demo" / "pallet_sorting_line" / "full_chain_schema.json"
    output_path = config.default_output_dir / "scene_behavior_graph.generated.json"
    state = invoke_agent(
        {
            "scene_document_ref": str(scene_path),
            "user_goal_raw": "传送带先将托盘运到指定位置，然后两个机械臂持续分拣托盘上的物料到出料传送带，并在出料传送带满载时暂停对应机械臂。",
            "output_path": str(output_path),
        },
        config=config,
    )
    print(state.get("explanation", ""))
    print(f"Generated: {Path(state.get('output_path', output_path)).resolve()}")


if __name__ == "__main__":
    main()
