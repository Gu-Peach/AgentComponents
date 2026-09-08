from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.agent.compiler import (
    CapabilityIndexer,
    GuardianValidator,
    IntentParser,
    SlotResolver,
    behavior_graph_artifact,
    parameter_binding_artifact,
    readonly_diagnostic_artifact,
    topology_completion_artifacts,
)
from app.agent.contracts import AgentArtifactContract, AgentState, ArtifactSchemaValidator, PatchEnvelope
from app.agent.diagnostics import runtime_diagnostic_artifact
from app.agent.events import AgentEventEmitter
from app.agent.graph import AgentGraphDefinition
from app.agent.scenarios import scenario_experiment_artifact
from app.agent.tools import ArtifactReader, ArtifactWriter, DeviceSpecReader, EventLogReader, PatchApplier, RuntimeSnapshotReader, SceneReader, TopologyReader
from app.core.errors import AppError, NotFoundError, RevisionConflictError
from app.db import models
from app.repositories.sql import AgentRepository, SceneRepository
from app.schemas.domain import AgentRunCreate
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore
from app.services.scene_service import SceneService


class AgentService:
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.runtime_store = runtime_store
        self.repo = AgentRepository(db)
        self.scenes = SceneRepository(db)
        self.events = AgentEventEmitter(self.repo)
        self.artifacts = ArtifactWriter(self.repo)
        self.schema_validator = ArtifactSchemaValidator()
        self.guardian = GuardianValidator()
        self.graph = AgentGraphDefinition()

    def create_run(self, project_id: str, payload: AgentRunCreate) -> models.AgentRun:
        scene_record = SceneReader(self.db).read(project_id, payload.base_scene_revision)
        scene_doc = scene_record["document"]
        base_revision = int(scene_record["revision"])
        run = models.AgentRun(
            id=new_id("agrun"),
            project_id=project_id,
            scene_id=scene_record["scene_id"],
            base_scene_revision=base_revision,
            status="running",
            user_message=payload.user_message,
        )
        self.repo.add_run(run)
        self.db.flush()
        self.events.emit(run.id, "agent.run_created", {"project_id": project_id, "scene_id": run.scene_id, "base_scene_revision": base_revision, "graph": self.graph.as_dict()})

        state = AgentState(run_id=run.id, project_id=project_id, scene_id=run.scene_id, user_message=payload.user_message, base_scene_revision=base_revision, scene=scene_doc)
        try:
            self._execute_graph(state, payload)
        except Exception as exc:
            error = {"type": exc.__class__.__name__, "message": str(exc)}
            self.repo.update_run_status(run, "failed", error=error, final_response={"message": "Agent run failed before final artifact emission.", "error": error})
            self.db.commit()
            raise

        checkpoint = self._checkpoint(state)
        self.repo.update_run_status(run, "completed", intent=state.intent, checkpoint=checkpoint, repair_attempts=state.repair_attempts, final_response=state.final_response)
        self.events.emit(run.id, "agent.finalized", state.final_response or {})
        self.db.commit()
        self.db.refresh(run)
        return run

    def get_run(self, agent_run_id: str) -> models.AgentRun:
        run = self.repo.get_run(agent_run_id)
        if not run:
            raise NotFoundError("AgentRun", agent_run_id)
        return run

    def list_artifacts(self, agent_run_id: str) -> list[models.AgentArtifact]:
        self.get_run(agent_run_id)
        return ArtifactReader(self.repo).read_for_run(agent_run_id)

    def list_events(self, agent_run_id: str) -> list[models.AgentEvent]:
        self.get_run(agent_run_id)
        return self.repo.list_events(agent_run_id)

    def apply_artifact(self, agent_run_id: str, artifact_id: str, expected_base_revision: int, *, approved_by_user: bool = False) -> dict[str, Any]:
        self.get_run(agent_run_id)
        return PatchApplier(self.db, self.repo).apply(artifact_id, expected_base_revision, approved_by_user=approved_by_user)

    def cancel_run(self, agent_run_id: str) -> models.AgentRun:
        run = self.get_run(agent_run_id)
        if run.status not in {"completed", "failed", "cancelled"}:
            run.status = "cancelled"
            self.events.emit(run.id, "agent.cancelled", {"reason": "user_requested"})
            self.db.commit()
        return run

    def resume_run(self, agent_run_id: str) -> models.AgentRun:
        run = self.get_run(agent_run_id)
        if run.status == "cancelled":
            run.status = "completed"
            run.final_response = run.final_response or {"message": "Agent run resumed from checkpoint; no pending node work remained.", "checkpoint": run.checkpoint or {}}
            self.events.emit(run.id, "agent.finalized", {"resumed": True, "checkpoint": run.checkpoint or {}})
            self.db.commit()
        return run

    def _execute_graph(self, state: AgentState, payload: AgentRunCreate) -> None:
        assert state.scene is not None
        scene_doc = state.scene
        self.events.emit(state.run_id, "agent.scene_loaded", {"scene_id": state.scene_id, "revision": state.base_scene_revision, "instances": len(scene_doc.get("instances", []))})

        specs = DeviceSpecReader(self.db).read_for_scene(scene_doc)
        state.device_specs = specs
        capability_index = CapabilityIndexer().build(scene_doc, specs)
        self.events.emit(state.run_id, "agent.device_specs_loaded", {"spec_ids": sorted(specs), "capability_counts": capability_index["counts"]})

        topology_record = TopologyReader(self.db).read(state.scene_id, state.base_scene_revision)
        if topology_record:
            topology = topology_record["document"]
            self.events.emit(state.run_id, "agent.topology_loaded", {"topology_id": topology_record["topology_id"], "scene_revision": topology_record["scene_revision"]})
        else:
            rebuilt = SceneService(self.db).rebuild_topology(state.project_id)
            topology = rebuilt["document"]
            self.events.emit(state.run_id, "agent.topology_built", {"topology_id": rebuilt["topology_id"], "scene_revision": rebuilt["scene_revision"]})
        state.topology = topology

        intent = IntentParser().parse(payload.user_message, simulation_run_id=payload.simulation_run_id, document_text=payload.document_text)
        state.intent = intent
        self.events.emit(state.run_id, "agent.intent_parsed", intent)

        slots = SlotResolver().resolve(scene_doc, topology, payload.user_message)
        state.resolved_slots = slots
        self.events.emit(state.run_id, "agent.slots_resolved", slots)

        candidates = self._route_task(state, payload)
        if not candidates:
            candidates = [readonly_diagnostic_artifact(scene_doc, specs, topology)]

        stored_artifacts = []
        for artifact in candidates:
            self._validate_candidate(artifact, scene_doc, specs)
            stored = self.artifacts.write(state.run_id, state.scene_id, artifact)
            stored_artifacts.append(stored)
            if stored.validation_report.get("valid"):
                self.events.emit(state.run_id, "agent.validation_passed", {"artifact_id": stored.id, "artifact_type": stored.artifact_type})
            else:
                self.events.emit(state.run_id, "agent.validation_failed", {"artifact_id": stored.id, "artifact_type": stored.artifact_type, "issues": stored.validation_report.get("issues", [])})
            if stored.artifact_type.endswith("_patch"):
                self.events.emit(state.run_id, "agent.patch_staged", {"artifact_id": stored.id, "artifact_type": stored.artifact_type, "approval_required": stored.approval_required})
                if stored.approval_required:
                    self.events.emit(state.run_id, "agent.waiting_for_user_review", {"artifact_id": stored.id, "risk": stored.payload.get("risk")})

        state.candidate_artifacts = [
            AgentArtifactContract(
                artifact_id=artifact.id,
                artifact_type=artifact.artifact_type,  # type: ignore[arg-type]
                base_scene_revision=artifact.base_scene_revision,
                payload=artifact.payload,
                confidence=artifact.confidence,
                approval_required=artifact.approval_required,
            )
            for artifact in stored_artifacts
        ]
        state.final_response = self._final_response(state, stored_artifacts)

        if payload.mode == "auto_apply":
            self._auto_apply_safe_patches(stored_artifacts, state.base_scene_revision)

    def _route_task(self, state: AgentState, payload: AgentRunCreate) -> list[AgentArtifactContract]:
        scene_doc = state.scene or {}
        specs = state.device_specs
        topology = state.topology
        intent_type = state.intent.get("intent_type")
        candidates: list[AgentArtifactContract] = [readonly_diagnostic_artifact(scene_doc, specs, topology)]

        if intent_type in {"topology_completion", "behavior_graph", "query_scene"} and self._needs_topology_completion(scene_doc):
            candidates.extend(topology_completion_artifacts(scene_doc, specs))
        if intent_type in {"behavior_graph", "topology_completion", "query_scene"}:
            behavior_artifact = behavior_graph_artifact(scene_doc, specs, topology, payload.user_message)
            candidates.append(behavior_artifact)
            self.events.emit(state.run_id, "agent.behavior_graph_created", {"artifact_type": behavior_artifact.artifact_type, "valid": behavior_artifact.validation_report.valid})
        if intent_type == "parameter_fill" or payload.document_text:
            parameter_artifact = parameter_binding_artifact(scene_doc, specs, "\n".join(filter(None, [payload.user_message, payload.document_text or ""])))
            if parameter_artifact:
                candidates.append(parameter_artifact)
                self.events.emit(state.run_id, "agent.parameters_extracted", {"artifact_type": parameter_artifact.artifact_type})
        if intent_type == "runtime_diagnosis":
            snapshot = RuntimeSnapshotReader(self.db, self.runtime_store).read(payload.simulation_run_id)
            events = EventLogReader(self.db, self.runtime_store).read(payload.simulation_run_id, window=100)
            diagnostic, repairs = runtime_diagnostic_artifact(scene_doc, specs, snapshot, events)
            candidates.append(diagnostic)
            limited_repairs = repairs[:2]
            state.repair_attempts = len(limited_repairs)
            candidates.extend(limited_repairs)
            if len(repairs) > len(limited_repairs):
                candidates.append(
                    AgentArtifactContract(
                        artifact_type="question_set",
                        base_scene_revision=int(scene_doc.get("revision", 0)),
                        payload={"questions": [{"question_id": "repair_limit_reached", "prompt": "已达到自动修复候选上限，请确认优先应用哪一个修复。"}], "dropped_repair_count": len(repairs) - len(limited_repairs)},
                        confidence=0.6,
                        approval_required=True,
                    )
                )
            self.events.emit(state.run_id, "agent.runtime_observation_diagnosed", {"can_auto_repair": bool(limited_repairs), "repair_count": len(limited_repairs)})
        if intent_type == "scenario_compare":
            candidates.append(scenario_experiment_artifact(scene_doc, payload.scenario_count))
            self.events.emit(state.run_id, "agent.scenario_plan_created", {"scenario_count": payload.scenario_count})
        return candidates

    def _validate_candidate(self, artifact: AgentArtifactContract, scene_doc: dict[str, Any], specs: dict[str, dict[str, Any]]) -> None:
        schema_report = self.schema_validator.validate_artifact(artifact)
        if not schema_report.valid:
            artifact.validation_report = schema_report
            return
        if artifact.artifact_type == "scene_behavior_graph_patch":
            envelope = PatchEnvelope.model_validate(artifact.payload)
            patch_report = self.guardian.validate_patch(artifact.artifact_type, envelope, scene_doc, specs)
            graph_issues = []
            graph_summary = {}
            for operation in envelope.operations:
                value = operation.value or {}
                graph = value.get("graph") if isinstance(value, dict) else None
                if graph:
                    graph_report = self.guardian.validate_behavior_graph(graph)
                    graph_issues.extend(issue.model_dump(mode="json") for issue in graph_report.issues)
                    graph_summary.update({f"behavior_graph_{key}": value for key, value in graph_report.summary.items()})
            artifact.validation_report = patch_report.from_issues(
                [issue.model_dump(mode="json") for issue in patch_report.issues] + graph_issues,
                {**patch_report.summary, **graph_summary},
            )
        elif artifact.artifact_type.endswith("_patch"):
            envelope = PatchEnvelope.model_validate(artifact.payload)
            artifact.validation_report = self.guardian.validate_patch(artifact.artifact_type, envelope, scene_doc, specs)
        elif artifact.artifact_type == "diagnostic_report":
            artifact.validation_report = schema_report
        elif artifact.artifact_type == "scenario_experiment_plan":
            artifact.validation_report = schema_report

    @staticmethod
    def _needs_topology_completion(scene_doc: dict[str, Any]) -> bool:
        return bool(scene_doc.get("instances")) and (not scene_doc.get("physical_edges") or not scene_doc.get("process_edges") or not scene_doc.get("signal_edges"))

    def _auto_apply_safe_patches(self, artifacts: list[models.AgentArtifact], base_revision: int) -> None:
        current_revision = base_revision
        for artifact in artifacts:
            if not artifact.artifact_type.endswith("_patch") or artifact.approval_required or not artifact.validation_report.get("valid"):
                continue
            try:
                result = PatchApplier(self.db, self.repo).apply(artifact.id, current_revision, approved_by_user=True)
            except (AppError, RevisionConflictError):
                continue
            if result.get("applied"):
                current_revision = result["new_revision"]

    @staticmethod
    def _final_response(state: AgentState, artifacts: list[models.AgentArtifact]) -> dict[str, Any]:
        valid_artifacts = [artifact for artifact in artifacts if artifact.validation_report.get("valid")]
        invalid_artifacts = [artifact for artifact in artifacts if not artifact.validation_report.get("valid")]
        patch_artifacts = [artifact for artifact in artifacts if artifact.artifact_type.endswith("_patch")]
        return {
            "message": "Agent run completed with candidate artifacts staged for validation/review.",
            "intent": deepcopy(state.intent),
            "resolved_slots": deepcopy(state.resolved_slots),
            "artifact_count": len(artifacts),
            "valid_artifact_count": len(valid_artifacts),
            "invalid_artifact_count": len(invalid_artifacts),
            "patch_artifact_count": len(patch_artifacts),
            "approval_required_count": sum(1 for artifact in artifacts if artifact.approval_required),
            "artifact_ids": [artifact.id for artifact in artifacts],
        }

    def _checkpoint(self, state: AgentState) -> dict[str, Any]:
        return {
            "current_node": "EmitResultNode",
            "completed_nodes": self.graph.node_names(),
            "scene_id": state.scene_id,
            "base_scene_revision": state.base_scene_revision,
            "intent": deepcopy(state.intent),
            "resolved_slots": deepcopy(state.resolved_slots),
            "repair_attempts": state.repair_attempts,
            "candidate_artifact_count": len(state.candidate_artifacts),
        }
