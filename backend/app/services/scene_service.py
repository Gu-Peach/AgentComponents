from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError, RevisionConflictError
from app.db import models
from app.repositories.sql import DeviceSpecRepository, ProjectRepository, SceneRepository
from app.schemas.domain import CompileInterfacesRequest, EdgeCreate, EdgeDelete, InstanceCreate, InstanceDelete, InstancePatch, SignalEdgeCreate
from app.services.ids import new_id
from app.services.interface_compiler import InterfaceCompiler
from app.services.topology_builder import TopologyBuilder
from app.services.validation import build_scene_context, validate_physical_edge, validate_process_edge, validate_signal_edge


class SceneService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.projects = ProjectRepository(db)
        self.scenes = SceneRepository(db)
        self.device_specs = DeviceSpecRepository(db)

    def get_scene_for_project(self, project_id: str) -> models.Scene:
        if not self.projects.get(project_id):
            raise NotFoundError("Project", project_id)
        scene = self.scenes.get_by_project(project_id)
        if not scene:
            raise NotFoundError("Scene", project_id)
        return scene

    def add_instance(self, project_id: str, payload: InstanceCreate) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        spec = self.device_specs.get(payload.spec_id)
        if not spec:
            raise NotFoundError("DeviceSpec", payload.spec_id)
        document = deepcopy(scene.current_document)
        instance_id = payload.instance_id or new_id(spec.device_type)
        if any(item.get("instance_id") == instance_id for item in document.get("instances", [])):
            raise AppError("INSTANCE_ALREADY_EXISTS", f"Instance already exists: {instance_id}", 409)
        instance = {
            "instance_id": instance_id,
            "spec_id": payload.spec_id,
            "device_type": payload.device_type or spec.device_type,
            "display_name": payload.display_name or spec.display_name,
            "transform": payload.transform.model_dump(),
            "param_overrides": payload.param_overrides,
            "visible": payload.visible,
            "locked": payload.locked,
            "semantic_tags": payload.semantic_tags,
        }
        document.setdefault("instances", []).append(instance)
        self._invalidate_topology(document)
        return self._save_scene(scene, document, "scene.instance_added", {"instance": instance})

    def patch_instance(self, project_id: str, instance_id: str, payload: InstancePatch) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        document = deepcopy(scene.current_document)
        instance = self._find_instance(document, instance_id)
        for key in ["display_name", "visible", "locked", "semantic_tags"]:
            value = getattr(payload, key)
            if value is not None:
                instance[key] = value
        if payload.transform is not None:
            instance["transform"] = payload.transform.model_dump()
        if payload.param_overrides is not None:
            instance["param_overrides"] = payload.param_overrides
        self._invalidate_topology(document)
        return self._save_scene(scene, document, "scene.instance_updated", {"instance_id": instance_id})

    def delete_instance(self, project_id: str, instance_id: str, payload: InstanceDelete) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        document = deepcopy(scene.current_document)
        self._find_instance(document, instance_id)
        incident = self._incident_edges(document, instance_id)
        if incident and payload.delete_policy == "reject_if_connected":
            raise AppError("INSTANCE_CONNECTED", "Instance still has connected edges.", 409, {"incident_edges": incident})
        if incident and payload.delete_policy == "stage_for_confirmation":
            return {
                "scene_id": scene.id,
                "previous_revision": scene.revision,
                "new_revision": scene.revision,
                "event_id": "dry_run",
                "document": document,
                "warnings": [{"severity": "warning", "code": "DELETE_CONFIRMATION_REQUIRED", "incident_edges": incident}],
            }
        document["instances"] = [item for item in document.get("instances", []) if item.get("instance_id") != instance_id]
        if payload.delete_policy == "delete_incident_edges":
            for key in ["process_edges", "physical_edges", "signal_edges"]:
                document[key] = [edge for edge in document.get(key, []) if edge.get("edge_id") not in incident]
        self._invalidate_topology(document)
        return self._save_scene(scene, document, "scene.instance_deleted", {"instance_id": instance_id, "incident_edges": incident})

    def list_edges(self, project_id: str, edge_kind: Literal["process", "physical", "signal"]) -> list[dict[str, Any]]:
        scene = self.get_scene_for_project(project_id)
        return scene.current_document.get(self._edge_section(edge_kind), [])

    def create_edge(self, project_id: str, edge_kind: Literal["process", "physical", "signal"], payload: EdgeCreate | SignalEdgeCreate) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        document = deepcopy(scene.current_document)
        specs = self._specs_for_scene(document)
        ctx = build_scene_context(document, specs)
        if edge_kind == "process":
            issues = validate_process_edge(ctx, payload.source, payload.target)
            edge = self._process_edge(payload)
        elif edge_kind == "physical":
            issues = validate_physical_edge(ctx, payload.source, payload.target)
            edge = self._physical_edge(payload)
        else:
            assert isinstance(payload, SignalEdgeCreate)
            issues = validate_signal_edge(ctx, payload.source, payload.target, payload.transform)
            edge = self._signal_edge(payload)
        if any(issue.get("severity") == "error" for issue in issues):
            raise AppError("EDGE_VALIDATION_FAILED", "Edge validation failed.", 422, {"issues": issues})
        section = self._edge_section(edge_kind)
        if any(item.get("edge_id") == edge["edge_id"] for item in document.get(section, [])):
            raise AppError("EDGE_ALREADY_EXISTS", f"Edge already exists: {edge['edge_id']}", 409)
        document.setdefault(section, []).append(edge)
        self._invalidate_topology(document)
        return self._save_scene(scene, document, f"scene.{edge_kind}_edge_added", {"edge": edge}, issues)

    def delete_edge(self, project_id: str, edge_kind: Literal["process", "physical", "signal"], edge_id: str, payload: EdgeDelete) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        document = deepcopy(scene.current_document)
        section = self._edge_section(edge_kind)
        before = len(document.get(section, []))
        document[section] = [edge for edge in document.get(section, []) if edge.get("edge_id") != edge_id]
        if before == len(document[section]):
            raise NotFoundError("Edge", edge_id)
        self._invalidate_topology(document)
        return self._save_scene(scene, document, f"scene.{edge_kind}_edge_deleted", {"edge_id": edge_id})

    def compile_interfaces(self, project_id: str, payload: CompileInterfacesRequest) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        self._check_revision(scene, payload.base_revision)
        document = deepcopy(scene.current_document)
        compiler = InterfaceCompiler()
        result = compiler.compile(document, self._specs_for_scene(document))
        if payload.mode == "dry_run":
            return result
        previous_revision = scene.revision
        for key, result_key in [("physical_edges", "compiled_physical_edges"), ("signal_edges", "compiled_signal_edges")]:
            existing = {(edge.get("source"), edge.get("target")) for edge in document.get(key, [])}
            for edge in result[result_key]:
                if (edge.get("source"), edge.get("target")) not in existing:
                    document.setdefault(key, []).append(edge)
        self._invalidate_topology(document)
        saved = self._save_scene(scene, document, "scene.interfaces_compiled", result)
        saved["compiled_physical_edges"] = result["compiled_physical_edges"]
        saved["compiled_signal_edges"] = result["compiled_signal_edges"]
        saved["previous_revision"] = previous_revision
        return saved

    def rebuild_topology(self, project_id: str) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        document = deepcopy(scene.current_document)
        topology = TopologyBuilder().build(document, self._specs_for_scene(document))
        row = self.db.get(models.SceneTopology, topology["graph_id"])
        if row:
            row.scene_revision = scene.revision
            row.document = topology
        else:
            row = models.SceneTopology(id=topology["graph_id"], scene_id=scene.id, scene_revision=scene.revision, graph_hash=None, document=topology)
            self.scenes.save_topology(row)
        document.setdefault("derived_artifacts", {})["topology_graph"] = {
            "graph_id": topology["graph_id"],
            "schema": "docs/business/SimulationSchema/5.TopologyGraph/schema.json",
            "source_scene_revision": scene.revision,
            "status": "valid" if not any(w.get("severity") == "error" for w in topology.get("warnings", [])) else "invalid",
        }
        scene.current_document = document
        self.db.commit()
        return {"topology_id": row.id, "scene_id": scene.id, "scene_revision": scene.revision, "document": topology}

    def get_latest_topology(self, project_id: str) -> dict[str, Any]:
        scene = self.get_scene_for_project(project_id)
        topology = self.scenes.latest_topology(scene.id)
        if not topology:
            return self.rebuild_topology(project_id)
        return {"topology_id": topology.id, "scene_id": scene.id, "scene_revision": topology.scene_revision, "document": topology.document}

    def reachability(self, project_id: str, source: str, target: str, graph: str = "process_graph") -> dict[str, Any]:
        topology = self.get_latest_topology(project_id)["document"]
        reachable = TopologyBuilder().is_reachable(topology, source, target, graph)
        return {"source": source, "target": target, "graph": graph, "reachable": reachable}

    def _save_scene(self, scene: models.Scene, document: dict[str, Any], event_type: str, payload: dict[str, Any], warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        previous = scene.revision
        new_revision = previous + 1
        document["revision"] = new_revision
        scene.revision = new_revision
        scene.current_document = document
        event = models.SceneEvent(id=new_id("evt"), scene_id=scene.id, revision=new_revision, event_type=event_type, payload=payload)
        self.scenes.add_event(event)
        self.db.commit()
        return {"scene_id": scene.id, "previous_revision": previous, "new_revision": new_revision, "event_id": event.id, "document": document, "warnings": warnings or []}

    @staticmethod
    def _check_revision(scene: models.Scene, base_revision: int) -> None:
        if scene.revision != base_revision:
            raise RevisionConflictError(base_revision, scene.revision)

    @staticmethod
    def _find_instance(document: dict[str, Any], instance_id: str) -> dict[str, Any]:
        for instance in document.get("instances", []):
            if instance.get("instance_id") == instance_id:
                return instance
        raise NotFoundError("Instance", instance_id)

    @staticmethod
    def _incident_edges(document: dict[str, Any], instance_id: str) -> list[str]:
        incident: list[str] = []
        prefix = f"{instance_id}."
        for key in ["process_edges", "physical_edges", "signal_edges"]:
            for edge in document.get(key, []):
                if str(edge.get("source", "")).startswith(prefix) or str(edge.get("target", "")).startswith(prefix):
                    incident.append(edge.get("edge_id"))
        return incident

    def _specs_for_scene(self, document: dict[str, Any]) -> dict[str, dict[str, Any]]:
        specs: dict[str, dict[str, Any]] = {}
        for instance in document.get("instances", []):
            spec_id = instance.get("spec_id")
            if spec_id and spec_id not in specs:
                spec = self.device_specs.get(spec_id)
                if spec:
                    specs[spec_id] = spec.document
        return specs

    @staticmethod
    def _invalidate_topology(document: dict[str, Any]) -> None:
        document.setdefault("derived_artifacts", {}).setdefault("topology_graph", {})["status"] = "invalid"

    @staticmethod
    def _edge_section(edge_kind: str) -> str:
        return {"process": "process_edges", "physical": "physical_edges", "signal": "signal_edges"}[edge_kind]

    @staticmethod
    def _process_edge(payload: EdgeCreate) -> dict[str, Any]:
        return {
            "edge_id": payload.edge_id or new_id("proc"),
            "source": payload.source,
            "target": payload.target,
            "edge_type": payload.edge_type,
            "material_classes": payload.metadata.get("material_classes", ["workpiece", "workpiece_carrier"]),
            "priority": payload.metadata.get("priority", 100),
            "conditions": payload.metadata.get("conditions", []),
            "compiled_physical_edges": payload.metadata.get("compiled_physical_edges", []),
            "compiled_signal_edges": payload.metadata.get("compiled_signal_edges", []),
        }

    @staticmethod
    def _physical_edge(payload: EdgeCreate) -> dict[str, Any]:
        return {
            "edge_id": payload.edge_id or new_id("phys"),
            "source": payload.source,
            "target": payload.target,
            "edge_type": payload.edge_type or "physical_connection",
            "connection_method": payload.metadata.get("connection_method", "manual"),
            "compiled_from": payload.metadata.get("compiled_from"),
            "is_inferred": payload.metadata.get("is_inferred", False),
            "confidence": payload.metadata.get("confidence", 1.0),
            "compatibility_result": payload.metadata.get("compatibility_result", {"status": "not_checked", "matched_fields": [], "missing_fields": []}),
            "snap_result": payload.metadata.get("snap_result", {"distance_m": None, "angle_deg": None, "within_tolerance": "not_checked", "retain_offset": False}),
        }

    @staticmethod
    def _signal_edge(payload: SignalEdgeCreate) -> dict[str, Any]:
        edge_id = payload.edge_id or new_id("sig")
        return {
            "edge_id": edge_id,
            "source": payload.source,
            "target": payload.target,
            "edge_type": payload.edge_type,
            "delivery": payload.delivery,
            "trigger": payload.trigger,
            "transform": payload.transform,
            "timeout_ms": payload.timeout_ms,
            "on_timeout": payload.on_timeout,
            "enabled": payload.enabled,
            "route_id": payload.metadata.get("route_id") or f"route_{edge_id}",
        }
