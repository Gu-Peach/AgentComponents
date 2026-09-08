from __future__ import annotations

from copy import deepcopy
from statistics import mean
from typing import Any

from app.agent.contracts import AgentArtifactContract
from app.schemas.domain import SimulationRunCreate
from app.services.simulation_service import SimulationService


class ScenarioGenerator:
    def generate(self, scene_doc: dict[str, Any], count: int = 2) -> list[dict[str, Any]]:
        variants = [self._base_variant(scene_doc)]
        if len(variants) < count:
            variants.append(self._speed_variant(scene_doc, multiplier=1.25))
        if len(variants) < count:
            variants.append(self._capacity_variant(scene_doc, increment=1))
        while len(variants) < count:
            variants.append(self._speed_variant(scene_doc, multiplier=1.0 + 0.1 * len(variants)))
        return variants[:count]

    @staticmethod
    def _base_variant(scene_doc: dict[str, Any]) -> dict[str, Any]:
        return {
            "variant_id": "baseline",
            "description": "Current scene parameters without structural changes.",
            "base_scene_revision": scene_doc.get("revision", 0),
            "patch_operations": [],
        }

    @staticmethod
    def _speed_variant(scene_doc: dict[str, Any], multiplier: float) -> dict[str, Any]:
        operations: list[dict[str, Any]] = []
        for index, instance in enumerate(scene_doc.get("instances", [])):
            if instance.get("device_type") != "conveyor":
                continue
            current = instance.get("param_overrides", {}).get("speed_mps", 0.4)
            operations.append({"op": "add", "path": f"/instances/{index}/param_overrides/speed_mps", "value": round(float(current) * multiplier, 3)})
        return {
            "variant_id": f"conveyor_speed_x{multiplier:.2f}".replace(".", "_"),
            "description": f"Increase conveyor speed by {round((multiplier - 1) * 100)}%.",
            "base_scene_revision": scene_doc.get("revision", 0),
            "patch_operations": operations,
        }

    @staticmethod
    def _capacity_variant(scene_doc: dict[str, Any], increment: int) -> dict[str, Any]:
        operations: list[dict[str, Any]] = []
        for index, instance in enumerate(scene_doc.get("instances", [])):
            if instance.get("device_type") != "conveyor":
                continue
            current = instance.get("param_overrides", {}).get("capacity", 3)
            operations.append({"op": "add", "path": f"/instances/{index}/param_overrides/capacity", "value": int(current) + increment})
        return {
            "variant_id": f"buffer_capacity_plus_{increment}",
            "description": f"Increase conveyor buffer capacity by {increment}.",
            "base_scene_revision": scene_doc.get("revision", 0),
            "patch_operations": operations,
        }


class MetricsReader:
    def summarize(self, simulation_runs: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = [run.get("metrics_summary") or {} for run in simulation_runs]
        numeric_keys = sorted({key for metric in metrics for key, value in metric.items() if isinstance(value, (int, float))})
        return {key: mean(float(metric.get(key, 0)) for metric in metrics) for key in numeric_keys} if metrics else {}


class SimulationSubmitter:
    def __init__(self, simulation_service: SimulationService) -> None:
        self.simulation_service = simulation_service

    def submit(self, project_id: str, base_scene_revision: int, variant: dict[str, Any]) -> dict[str, Any]:
        initial_snapshot = {"scenario_variant": deepcopy(variant), "event_queue": [], "signal_values": {}}
        run = self.simulation_service.create_run(project_id, SimulationRunCreate(base_scene_revision=base_scene_revision, initial_snapshot=initial_snapshot))
        return {"run_id": run.id, "variant_id": variant.get("variant_id"), "status": run.status, "base_scene_revision": run.base_scene_revision}


class BottleneckAnalyzer:
    def analyze(self, scene_doc: dict[str, Any], metrics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        bottlenecks: list[dict[str, Any]] = []
        for instance in scene_doc.get("instances", []):
            overrides = instance.get("param_overrides", {})
            if instance.get("device_type") == "conveyor" and int(overrides.get("capacity", 3)) <= 1:
                bottlenecks.append({"instance_id": instance.get("instance_id"), "reason": "low_buffer_capacity", "evidence": {"capacity": overrides.get("capacity", 3)}})
            if instance.get("device_type") == "robot_arm" and float(overrides.get("speed", 1.0)) < 0.5:
                bottlenecks.append({"instance_id": instance.get("instance_id"), "reason": "slow_robot_motion", "evidence": {"speed": overrides.get("speed")}})
        if metrics and metrics.get("deadlock_count", 0) > 0:
            bottlenecks.append({"instance_id": None, "reason": "deadlock_observed", "evidence": {"deadlock_count": metrics["deadlock_count"]}})
        return bottlenecks


class RecommendationPlanner:
    def recommend(self, variants: list[dict[str, Any]], bottlenecks: list[dict[str, Any]]) -> dict[str, Any]:
        if any(item.get("reason") == "low_buffer_capacity" for item in bottlenecks):
            preferred = next((variant for variant in variants if variant["variant_id"].startswith("buffer_capacity")), variants[-1])
            return {"recommended_variant": preferred["variant_id"], "reason": "Capacity bottleneck detected; test buffer expansion first.", "confidence": 0.68}
        if len(variants) > 1:
            return {"recommended_variant": variants[1]["variant_id"], "reason": "No measured bottleneck yet; run a conservative speed sensitivity first.", "confidence": 0.55}
        return {"recommended_variant": variants[0]["variant_id"], "reason": "Only baseline is available.", "confidence": 0.4}


class AcceptanceAssertionBuilder:
    DEFAULT_ASSERTIONS = [
        {"assertion_id": "throughput_measured", "metric": "throughput", "operator": ">=", "target": None, "status": "needs_target"},
        {"assertion_id": "cycle_time_measured", "metric": "cycle_time", "operator": "<=", "target": None, "status": "needs_target"},
        {"assertion_id": "wip_measured", "metric": "WIP", "operator": "<=", "target": None, "status": "needs_target"},
        {"assertion_id": "utilization_measured", "metric": "utilization", "operator": "between", "target": None, "status": "needs_target"},
        {"assertion_id": "timeout_rate_measured", "metric": "timeout_rate", "operator": "<=", "target": None, "status": "needs_target"},
    ]

    def build(self, metrics: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        assertions = deepcopy(self.DEFAULT_ASSERTIONS)
        metrics = metrics or {}
        for assertion in assertions:
            metric = assertion["metric"]
            if metric in metrics:
                assertion["observed"] = metrics[metric]
                assertion["status"] = "observed_no_target"
        return assertions


class ScenarioReportWriter:
    def write(self, scene_doc: dict[str, Any], variants: list[dict[str, Any]], metrics: dict[str, Any] | None, bottlenecks: list[dict[str, Any]], recommendation: dict[str, Any]) -> AgentArtifactContract:
        payload = {
            "variants": variants,
            "metrics": {
                "requested": ["throughput", "cycle_time", "WIP", "waiting_time", "utilization", "blocked_time", "deadlock_count"],
                "observed_summary": deepcopy(metrics or {}),
            },
            "bottlenecks": bottlenecks,
            "tradeoffs": [],
            "assertions": AcceptanceAssertionBuilder().build(metrics),
            "recommendation_policy": recommendation,
            "model_confidence": recommendation.get("confidence", 0.5),
            "cannot_conclude": [] if metrics else ["No completed simulation metrics were supplied; recommendations are preflight hypotheses."],
        }
        return AgentArtifactContract(
            artifact_type="scenario_experiment_plan",
            base_scene_revision=int(scene_doc.get("revision", 0)),
            payload=payload,
            confidence=payload["model_confidence"],
            approval_required=True,
            source_trace=[{"kind": "scenario_report", "scene_id": scene_doc.get("scene_id"), "revision": scene_doc.get("revision", 0)}],
        )


def scenario_experiment_artifact(scene_doc: dict[str, Any], scenario_count: int = 2, metrics: dict[str, Any] | None = None) -> AgentArtifactContract:
    variants = ScenarioGenerator().generate(scene_doc, scenario_count)
    bottlenecks = BottleneckAnalyzer().analyze(scene_doc, metrics)
    recommendation = RecommendationPlanner().recommend(variants, bottlenecks)
    payload = {
        "variants": variants,
        "metrics": {
            "requested": ["throughput", "cycle_time", "WIP", "waiting_time", "utilization", "blocked_time", "deadlock_count"],
            "observed_summary": deepcopy(metrics or {}),
        },
        "bottlenecks": bottlenecks,
        "tradeoffs": [
            {"dimension": "speed", "risk": "Higher conveyor speed can move the bottleneck to robot utilization."},
            {"dimension": "capacity", "risk": "Higher buffers can improve throughput but increase WIP."},
        ],
        "assertions": AcceptanceAssertionBuilder().build(metrics),
        "recommendation_policy": recommendation,
        "model_confidence": recommendation["confidence"],
        "cannot_conclude": [] if metrics else ["No completed simulation metrics were supplied; recommendations are preflight hypotheses."],
    }
    return AgentArtifactContract(
        artifact_type="scenario_experiment_plan",
        base_scene_revision=int(scene_doc.get("revision", 0)),
        payload=payload,
        confidence=payload["model_confidence"],
        approval_required=True,
        source_trace=[{"kind": "scene", "scene_id": scene_doc.get("scene_id"), "revision": scene_doc.get("revision", 0)}],
    )
