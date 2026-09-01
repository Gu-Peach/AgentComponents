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
            "queue_wait": {
                "type": "queue_wait",
                "queue_scope": "conveyor_stop_points",
                "wait_when": "next_stop_point_occupied or downstream_unavailable",
                "resume_when": "stop_point_released or downstream_available",
            },
            "nearest_available_stop_point": {
                "type": "nearest_available_stop_point",
                "search_direction": "towards_exit",
                "fallback": "wait_at_nearest_upstream_stop_point",
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
        if "conveyor" in device_types:
            policies["conveyor_queue_wait"] = {
                "type": "queue_wait",
                "queue_scope": "conveyor_stop_points",
                "wait_when": "next_stop_point_occupied or downstream_unavailable",
                "resume_when": "stop_point_released or downstream_available",
            }
            policies["conveyor_stop_point_selection"] = {
                "type": "nearest_available_stop_point",
                "search_direction": "towards_exit",
                "fallback": "wait_at_nearest_upstream_stop_point",
            }
            policies["backpressure"] = {
                "type": "capacity_threshold",
                "blocked_when": "current_load >= max_capacity",
                "resume_when": "current_load <= resume_threshold",
                "pause_strategy": "pause_before_next_pick",
            }
            policies["downstream_release"] = {
                "type": "downstream_release",
                "release_when": "downstream_entry_available and exit_stop_point_occupied",
                "on_blocked": "queue_wait",
            }
        return policies
