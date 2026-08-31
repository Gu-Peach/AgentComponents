"""Reusable policy templates for SceneBehaviorGraph generation."""

from __future__ import annotations

from typing import Any


class PolicyLibrary:
    def default_policies(self) -> dict[str, Any]:
        return {
            "deterministic_priority": {
                "type": "deterministic_priority",
                "tie_breaker": "rule_id_lexicographic",
            },
            "resource_lock": {
                "type": "resource_lock",
                "lock_scope": "instance_resource",
                "on_conflict": "wait",
            },
            "deadlock_detection": {
                "type": "deadlock_detection",
                "condition": "no_enabled_behavior and completion_conditions_not_met",
                "emit": "observation.deadlock_detected",
            },
        }

    def infer_policies(self, scene_facts: dict[str, Any], process_modules: list[dict[str, Any]]) -> dict[str, Any]:
        policies = self.default_policies()
        device_types = {instance.get("device_type") for instance in scene_facts.get("instances", [])}
        material_count = len(scene_facts.get("materials", []))
        robot_count = sum(1 for instance in scene_facts.get("instances", []) if instance.get("device_type") == "robot_arm")
        conveyor_count = sum(1 for instance in scene_facts.get("instances", []) if instance.get("device_type") == "conveyor")
        if material_count > 0 and robot_count > 1:
            policies["claim_workpiece"] = {
                "type": "shared_pool_claim",
                "source_pool": "workpiece_pool",
                "mutual_exclusion": True,
                "claim_order": "deterministic_by_material_id",
            }
        if "conveyor" in device_types and conveyor_count > 1:
            policies["backpressure"] = {
                "type": "capacity_threshold",
                "blocked_when": "current_load >= max_capacity",
                "resume_when": "current_load <= resume_threshold",
                "pause_strategy": "pause_before_next_pick",
            }
        return policies
