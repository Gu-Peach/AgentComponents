from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agent.contracts import AgentArtifactContract
from app.agent.compiler import patch_artifact


OBSERVATION_TYPES = {
    "deadlock",
    "timeout",
    "target_not_reached",
    "resource_conflict",
    "capacity_blocked",
    "event_unconsumed",
    "action_failed",
    "completion_not_met",
    "metric_violation",
    "user_interrupt",
}


class ObservationClassifier:
    def classify(self, snapshot: dict[str, Any] | None, event_log: list[dict[str, Any]]) -> dict[str, Any]:
        haystack = " ".join(str(item).lower() for item in ([snapshot or {}] + event_log[-20:]))
        if "deadlock" in haystack or "no_enabled_behavior" in haystack:
            observation_type = "deadlock"
        elif "timeout" in haystack:
            observation_type = "timeout"
        elif "resource" in haystack and ("wait" in haystack or "lock" in haystack):
            observation_type = "resource_conflict"
        elif "blocked" in haystack or "capacity" in haystack:
            observation_type = "capacity_blocked"
        elif "unconsumed" in haystack or "unrouted" in haystack:
            observation_type = "event_unconsumed"
        elif "failed" in haystack or "error" in haystack:
            observation_type = "action_failed"
        else:
            observation_type = "completion_not_met"
        return {"observation_type": observation_type, "confidence": 0.74}


class TraceAnalyzer:
    def analyze(self, snapshot: dict[str, Any] | None, event_log: list[dict[str, Any]], scene_doc: dict[str, Any]) -> dict[str, Any]:
        snapshot = snapshot or {}
        signal_values = snapshot.get("signal_values", {})
        routed = [event for event in snapshot.get("event_queue", []) if event.get("type") == "routed_signal_event"]
        delivered = [event for event in snapshot.get("event_queue", []) if event.get("status") == "delivered"]
        signal_edges = scene_doc.get("signal_edges", [])
        unrouted_sources = [signal_id for signal_id in signal_values if not any(edge.get("source") == signal_id for edge in signal_edges)]
        waiting_resources = {key: value for key, value in snapshot.get("wait_queues", {}).items() if str(key).startswith("resource:") and value}
        return {
            "signal_values": deepcopy(signal_values),
            "routed_event_count": len(routed),
            "delivered_event_count": len(delivered),
            "unrouted_sources": unrouted_sources,
            "waiting_resources": waiting_resources,
            "recent_events": event_log[-10:],
            "active_actions": deepcopy(snapshot.get("active_actions", {})),
            "resource_locks": deepcopy(snapshot.get("resource_locks", {})),
        }


class RootCauseMapper:
    def map(self, classification: dict[str, Any], trace: dict[str, Any], scene_doc: dict[str, Any]) -> list[dict[str, Any]]:
        causes: list[dict[str, Any]] = []
        if trace.get("unrouted_sources"):
            causes.append(
                {
                    "cause_type": "missing_signal_route",
                    "message": "Runtime has source signals without matching SceneDocument.signal_edges routes.",
                    "signals": trace["unrouted_sources"],
                }
            )
        if trace.get("waiting_resources"):
            causes.append(
                {
                    "cause_type": "resource_lock_not_released",
                    "message": "One or more resource wait queues are blocked by active locks.",
                    "waiting_resources": trace["waiting_resources"],
                }
            )
        if classification.get("observation_type") == "deadlock" and not causes:
            causes.append(
                {
                    "cause_type": "no_enabled_behavior",
                    "message": "No enabled behavior was found while completion conditions were not met.",
                    "process_edges": len(scene_doc.get("process_edges", [])),
                    "signal_edges": len(scene_doc.get("signal_edges", [])),
                }
            )
        if not causes:
            causes.append({"cause_type": classification.get("observation_type"), "message": "Observation needs more runtime evidence to isolate a deterministic root cause."})
        return causes


class RepairPlanner:
    def plan(self, root_causes: list[dict[str, Any]], scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> list[AgentArtifactContract]:
        artifacts: list[AgentArtifactContract] = []
        for cause in root_causes:
            if cause.get("cause_type") != "missing_signal_route":
                continue
            for source in cause.get("signals", []):
                target = self._best_target_signal(source, scene_doc, specs)
                if not target:
                    continue
                source_safe = source.replace(".", "_")
                target_safe = target.replace(".", "_")
                edge = {
                    "edge_id": f"sig_repair_{source_safe}_to_{target_safe}",
                    "source": source,
                    "target": target,
                    "edge_type": "control_signal",
                    "delivery": "event",
                    "trigger": "on_rising_edge",
                    "transform": {"type": "identity"},
                    "timeout_ms": 30000,
                    "on_timeout": "raise_observation",
                    "enabled": True,
                    "route_id": f"route_sig_repair_{source_safe}_to_{target_safe}",
                }
                artifacts.append(
                    patch_artifact(
                        "signal_patch",
                        int(scene_doc.get("revision", 0)),
                        [{"op": "add", "path": "/signal_edges/-", "value": edge}],
                        "Repair runtime observation by adding the missing source-to-target signal route.",
                        0.76,
                        approval_required=False,
                        source_trace=[{"kind": "runtime_observation", "source_signal": source, "target_signal": target}],
                        risk="low",
                    )
                )
        return artifacts

    @staticmethod
    def _best_target_signal(source: str, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> str | None:
        source_port = source.split(".", 1)[-1]
        target_tokens = ["start_pick", "release_waiting_material", "resume_pick"] if "ready" in source_port or "done" in source_port else ["pause_pick"]
        for instance in scene_doc.get("instances", []):
            spec = specs.get(instance.get("spec_id"), {})
            for signal in spec.get("signal_ports", []):
                if signal.get("direction") not in {"input", "bidirectional"}:
                    continue
                if signal.get("port_id") in target_tokens:
                    return f"{instance.get('instance_id')}.{signal.get('port_id')}"
        return None


def runtime_diagnostic_artifact(scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]], snapshot: dict[str, Any] | None, event_log: list[dict[str, Any]]) -> tuple[AgentArtifactContract, list[AgentArtifactContract]]:
    classification = ObservationClassifier().classify(snapshot, event_log)
    trace = TraceAnalyzer().analyze(snapshot, event_log, scene_doc)
    root_causes = RootCauseMapper().map(classification, trace, scene_doc)
    repair_artifacts = RepairPlanner().plan(root_causes, scene_doc, specs)
    report = {
        "symptom": classification["observation_type"],
        "root_causes": root_causes,
        "evidence": trace,
        "affected_devices": _affected_devices(root_causes),
        "suggested_repairs": [artifact.payload for artifact in repair_artifacts],
        "can_auto_repair": bool(repair_artifacts),
        "safe_point_required": True,
    }
    artifact = AgentArtifactContract(
        artifact_type="diagnostic_report",
        base_scene_revision=int(scene_doc.get("revision", 0)),
        payload=report,
        confidence=classification["confidence"],
        approval_required=False,
        source_trace=[{"kind": "runtime_snapshot"}, {"kind": "event_log", "count": len(event_log)}],
    )
    return artifact, repair_artifacts


def _affected_devices(root_causes: list[dict[str, Any]]) -> list[str]:
    devices: set[str] = set()
    for cause in root_causes:
        for signal in cause.get("signals", []):
            if "." in signal:
                devices.add(signal.split(".", 1)[0])
        for resource in cause.get("waiting_resources", {}):
            raw = resource.removeprefix("resource:")
            devices.add(raw.split(".", 1)[0])
    return sorted(devices)
