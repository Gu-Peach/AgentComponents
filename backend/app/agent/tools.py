from __future__ import annotations

from copy import deepcopy
from typing import Any

from sqlalchemy.orm import Session

from app.agent.contracts import AgentArtifactContract, ArtifactSchemaValidator, PatchEnvelope, ValidationReport
from app.core.errors import AppError, NotFoundError, RevisionConflictError
from app.db import models
from app.repositories.sql import AgentRepository, DeviceSpecRepository, ProjectRepository, SceneRepository, SimulationRepository
from app.services.ids import new_id
from app.services.runtime_state import RuntimeStateStore


class SceneReader:
    def __init__(self, db: Session) -> None:
        self.projects = ProjectRepository(db)
        self.scenes = SceneRepository(db)

    def read(self, project_id: str, revision: int | None = None) -> dict[str, Any]:
        if not self.projects.get(project_id):
            raise NotFoundError("Project", project_id)
        scene = self.scenes.get_by_project(project_id)
        if not scene:
            raise NotFoundError("Scene", project_id)
        if revision is not None and scene.revision != revision:
            raise RevisionConflictError(revision, scene.revision)
        return {"scene_id": scene.id, "project_id": scene.project_id, "revision": scene.revision, "document": deepcopy(scene.current_document)}


class DeviceSpecReader:
    def __init__(self, db: Session) -> None:
        self.device_specs = DeviceSpecRepository(db)

    def read(self, spec_ids: list[str]) -> dict[str, dict[str, Any]]:
        specs: dict[str, dict[str, Any]] = {}
        for spec_id in dict.fromkeys(spec_ids):
            spec = self.device_specs.get(spec_id) or self.device_specs.get_by_key(spec_id)
            if spec:
                specs[spec.id] = deepcopy(spec.document)
        return specs

    def read_for_scene(self, scene_doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return self.read([instance.get("spec_id", "") for instance in scene_doc.get("instances", []) if instance.get("spec_id")])


class TopologyReader:
    def __init__(self, db: Session) -> None:
        self.scenes = SceneRepository(db)

    def read(self, scene_id: str, revision: int) -> dict[str, Any] | None:
        topology = self.scenes.latest_topology(scene_id)
        if not topology or topology.scene_revision != revision:
            return None
        return {"topology_id": topology.id, "scene_id": topology.scene_id, "scene_revision": topology.scene_revision, "document": deepcopy(topology.document)}


class ArtifactReader:
    def __init__(self, repo: AgentRepository) -> None:
        self.repo = repo

    def read_for_run(self, agent_run_id: str) -> list[models.AgentArtifact]:
        return self.repo.list_artifacts(agent_run_id)


class RuntimeSnapshotReader:
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.simulations = SimulationRepository(db)
        self.runtime_store = runtime_store

    def read(self, simulation_run_id: str | None) -> dict[str, Any] | None:
        if not simulation_run_id:
            return None
        run = self.simulations.get_run(simulation_run_id)
        if not run:
            raise NotFoundError("SimulationRun", simulation_run_id)
        return deepcopy(self.runtime_store.get_snapshot(simulation_run_id) or run.runtime_snapshot or {})


class EventLogReader:
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.simulations = SimulationRepository(db)
        self.runtime_store = runtime_store

    def read(self, simulation_run_id: str | None, window: int = 100, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not simulation_run_id:
            return []
        db_events = [
            {
                "event_id": event.id,
                "event_type": event.event_type,
                "sim_time_s": event.sim_time_s,
                "payload": deepcopy(event.payload),
                "source": "database",
            }
            for event in self.simulations.list_events(simulation_run_id)
        ]
        runtime_events = [{**deepcopy(event), "source": event.get("source", "runtime_store")} for event in self.runtime_store.get_events(simulation_run_id)]
        events = (db_events + runtime_events)[-window:]
        if filters and filters.get("event_type"):
            wanted = set(filters["event_type"] if isinstance(filters["event_type"], list) else [filters["event_type"]])
            events = [event for event in events if event.get("event_type") in wanted or event.get("type") in wanted]
        return events


class ArtifactWriter:
    def __init__(self, repo: AgentRepository) -> None:
        self.repo = repo
        self.validator = ArtifactSchemaValidator()

    def write(self, agent_run_id: str, scene_id: str, artifact: AgentArtifactContract) -> models.AgentArtifact:
        schema_validation = self.validator.validate_artifact(artifact)
        if not schema_validation.valid:
            merged_validation = schema_validation
        elif artifact.validation_report.issues or artifact.validation_report.summary:
            merged_validation = artifact.validation_report
        else:
            merged_validation = schema_validation
        row = models.AgentArtifact(
            id=artifact.artifact_id,
            agent_run_id=agent_run_id,
            scene_id=scene_id,
            artifact_type=artifact.artifact_type,
            base_scene_revision=artifact.base_scene_revision,
            status="candidate" if merged_validation.valid else "invalid",
            confidence=artifact.confidence,
            approval_required=artifact.approval_required,
            payload=deepcopy(artifact.payload),
            validation_report=merged_validation.as_dict(),
        )
        self.repo.add_artifact(row)
        self.repo.db.flush()
        return row


class PatchStager:
    def __init__(self, repo: AgentRepository) -> None:
        self.writer = ArtifactWriter(repo)

    def stage(self, agent_run_id: str, scene_id: str, artifact: AgentArtifactContract) -> models.AgentArtifact:
        if not artifact.artifact_type.endswith("_patch"):
            raise AppError("NOT_A_PATCH_ARTIFACT", "PatchStager only accepts patch artifacts.", 422, {"artifact_type": artifact.artifact_type})
        return self.writer.write(agent_run_id, scene_id, artifact)


class RuntimeControlTool:
    def __init__(self, db: Session, runtime_store: RuntimeStateStore) -> None:
        self.db = db
        self.runtime_store = runtime_store
        self.simulations = SimulationRepository(db)

    def pause(self, simulation_run_id: str, reason: str = "agent_requested_safe_point") -> dict[str, Any]:
        return self._set_status(simulation_run_id, "paused", reason)

    def resume(self, simulation_run_id: str, reason: str = "agent_repair_applied") -> dict[str, Any]:
        return self._set_status(simulation_run_id, "running", reason)

    def cancel(self, simulation_run_id: str, reason: str = "agent_cancel_requested") -> dict[str, Any]:
        return self._set_status(simulation_run_id, "cancelled", reason)

    def request_replan(self, simulation_run_id: str, reason: str, repair_artifact_id: str | None = None) -> dict[str, Any]:
        run = self.simulations.get_run(simulation_run_id)
        if not run:
            raise NotFoundError("SimulationRun", simulation_run_id)
        snapshot = deepcopy(self.runtime_store.get_snapshot(simulation_run_id) or run.runtime_snapshot or {})
        request = {"type": "agent_replan_requested", "reason": reason, "repair_artifact_id": repair_artifact_id}
        snapshot.setdefault("event_queue", []).append(request)
        self.runtime_store.put_snapshot(simulation_run_id, snapshot)
        run.runtime_snapshot = snapshot
        self.db.commit()
        return {"run_id": simulation_run_id, "status": run.status, "replan_requested": True, "event": request}

    def _set_status(self, simulation_run_id: str, status: str, reason: str) -> dict[str, Any]:
        run = self.simulations.get_run(simulation_run_id)
        if not run:
            raise NotFoundError("SimulationRun", simulation_run_id)
        run.status = status
        snapshot = deepcopy(self.runtime_store.get_snapshot(simulation_run_id) or run.runtime_snapshot or {})
        snapshot["runtime_control"] = {"status": status, "reason": reason}
        self.runtime_store.put_snapshot(simulation_run_id, snapshot)
        run.runtime_snapshot = snapshot
        self.db.commit()
        return {"run_id": simulation_run_id, "status": status, "reason": reason}


class SceneBehaviorGraphWriter:
    def __init__(self, repo: AgentRepository) -> None:
        self.writer = ArtifactWriter(repo)

    def write_candidate(self, agent_run_id: str, scene_id: str, artifact: AgentArtifactContract) -> models.AgentArtifact:
        if artifact.artifact_type != "scene_behavior_graph_patch":
            raise AppError("INVALID_BEHAVIOR_GRAPH_ARTIFACT", "SceneBehaviorGraphWriter only accepts scene_behavior_graph_patch artifacts.", 422)
        return self.writer.write(agent_run_id, scene_id, artifact)


class PatchApplier:
    """Apply validated Agent patch artifacts to SceneDocument with revision and approval checks."""

    def __init__(self, db: Session, repo: AgentRepository) -> None:
        self.db = db
        self.repo = repo
        self.scenes = SceneRepository(db)

    def apply(self, artifact_id: str, expected_base_revision: int, *, approved_by_user: bool = False) -> dict[str, Any]:
        artifact = self.repo.get_artifact(artifact_id)
        if not artifact:
            raise NotFoundError("AgentArtifact", artifact_id)
        if artifact.status == "applied":
            return {
                "artifact_id": artifact.id,
                "applied": False,
                "status": "already_applied",
                "scene_id": artifact.scene_id,
                "previous_revision": artifact.base_scene_revision,
                "new_revision": artifact.base_scene_revision,
                "validation_report": artifact.validation_report,
                "warnings": [],
            }
        if artifact.validation_report and not artifact.validation_report.get("valid", False):
            raise AppError("PATCH_VALIDATION_FAILED", "Only valid patch artifacts can be applied.", 422, {"validation_report": artifact.validation_report})
        envelope = PatchEnvelope.model_validate(artifact.payload)
        if envelope.base_scene_revision != expected_base_revision or artifact.base_scene_revision != expected_base_revision:
            raise RevisionConflictError(expected_base_revision, artifact.base_scene_revision)
        if artifact.approval_required and not approved_by_user:
            raise AppError("APPROVAL_REQUIRED", "This patch requires explicit user approval before applying.", 409, {"artifact_id": artifact.id, "risk": envelope.risk})
        scene = self.scenes.get(artifact.scene_id)
        if not scene:
            raise NotFoundError("Scene", artifact.scene_id)
        if scene.revision != expected_base_revision:
            raise RevisionConflictError(expected_base_revision, scene.revision)

        document = deepcopy(scene.current_document)
        for op in envelope.operations:
            self._apply_operation(document, op.model_dump(mode="json"))
        previous_revision = scene.revision
        new_revision = previous_revision + 1
        document["revision"] = new_revision
        document.setdefault("derived_artifacts", {}).setdefault("topology_graph", {})["status"] = "invalid"
        scene.current_document = document
        scene.revision = new_revision
        artifact.status = "applied"
        self.scenes.add_event(
            models.SceneEvent(
                id=new_id("evt"),
                scene_id=scene.id,
                revision=new_revision,
                event_type="agent.patch_applied",
                payload={"artifact_id": artifact.id, "patch_id": envelope.patch_id, "operations": [op.model_dump(mode="json") for op in envelope.operations]},
            )
        )
        self.repo.add_event(
            models.AgentEvent(
                id=new_id("agevt"),
                agent_run_id=artifact.agent_run_id,
                sequence=self.repo.next_event_sequence(artifact.agent_run_id),
                event_type="agent.patch_applied",
                payload={"artifact_id": artifact.id, "scene_revision": new_revision},
            )
        )
        self.db.commit()
        return {
            "artifact_id": artifact.id,
            "applied": True,
            "status": "applied",
            "scene_id": scene.id,
            "previous_revision": previous_revision,
            "new_revision": new_revision,
            "validation_report": artifact.validation_report,
            "warnings": [],
        }

    def _apply_operation(self, document: dict[str, Any], operation: dict[str, Any]) -> None:
        path = operation["path"]
        if not path.startswith("/"):
            raise AppError("INVALID_PATCH_PATH", "Patch operation path must be a JSON pointer.", 422, {"path": path})
        parent, key = self._resolve_parent(document, path)
        op = operation["op"]
        if op == "test":
            if self._read_value(parent, key) != operation.get("value"):
                raise AppError("PATCH_TEST_FAILED", "Patch test operation failed.", 409, {"path": path})
            return
        if op == "remove":
            if isinstance(parent, list):
                parent.pop(self._list_index(parent, key))
            else:
                parent.pop(key, None)
            return
        if op == "add":
            if isinstance(parent, list):
                if key == "-":
                    parent.append(operation.get("value"))
                else:
                    parent.insert(self._list_index(parent, key), operation.get("value"))
            else:
                parent[key] = operation.get("value")
            return
        if op == "replace":
            if isinstance(parent, list):
                parent[self._list_index(parent, key)] = operation.get("value")
            else:
                parent[key] = operation.get("value")
            return
        raise AppError("UNSUPPORTED_PATCH_OP", f"Unsupported patch operation: {op}", 422, {"operation": operation})

    def _resolve_parent(self, document: dict[str, Any], path: str) -> tuple[Any, str]:
        parts = [self._unescape_pointer(part) for part in path.strip("/").split("/") if part != ""]
        if not parts:
            raise AppError("INVALID_PATCH_PATH", "Patch operation cannot target document root.", 422, {"path": path})
        current: Any = document
        for part in parts[:-1]:
            if isinstance(current, list):
                current = current[self._list_index(current, part)]
            else:
                current = current.setdefault(part, {})
        return current, parts[-1]

    @staticmethod
    def _read_value(parent: Any, key: str) -> Any:
        if isinstance(parent, list):
            return parent[PatchApplier._list_index(parent, key)]
        return parent.get(key)

    @staticmethod
    def _list_index(items: list[Any], key: str) -> int:
        try:
            index = int(key)
        except ValueError as exc:
            raise AppError("INVALID_PATCH_PATH", f"List index must be numeric: {key}", 422) from exc
        if index < 0 or index >= len(items):
            raise AppError("INVALID_PATCH_PATH", f"List index out of range: {key}", 422)
        return index

    @staticmethod
    def _unescape_pointer(part: str) -> str:
        return part.replace("~1", "/").replace("~0", "~")
