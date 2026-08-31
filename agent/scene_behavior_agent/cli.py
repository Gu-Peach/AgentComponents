"""CLI entry point for generating SceneBehaviorGraph drafts."""

from __future__ import annotations

import argparse
from pathlib import Path

from .graph.runner import invoke_agent
from .schemas.config import AgentConfig, default_config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate SceneBehaviorGraph from SceneDocument and user goal.")
    parser.add_argument("--scene", required=True, help="Path to SceneDocument JSON or full_chain_schema JSON containing scene_document.")
    parser.add_argument("--goal", required=True, help="Natural language simulation goal.")
    parser.add_argument("--output", help="Output path for generated SceneBehaviorGraph JSON.")
    parser.add_argument("--manual-review", action="store_true", help="Disable auto approval at HumanReviewNode.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = default_config()
    if args.manual_review:
        config = AgentConfig(repo_root=config.repo_root, max_repair_attempts=config.max_repair_attempts, auto_approve=False)
    output = args.output or str(config.default_output_dir / "scene_behavior_graph.generated.json")
    final_state = invoke_agent(
        {
            "scene_document_ref": str(Path(args.scene).resolve()),
            "user_goal_raw": args.goal,
            "output_path": output,
        },
        config=config,
    )
    print(final_state.get("explanation", ""))
    if final_state.get("final_scene_behavior_graph"):
        print(f"Generated: {final_state.get('output_path')}")
    else:
        print("Graph was not finalized. Check validation_report or approval_status.")


if __name__ == "__main__":
    main()
