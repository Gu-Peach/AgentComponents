from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field, model_validator

from app.services.ids import new_id


JsonDict = dict[str, Any]

ArtifactType = Literal[
    "scene_patch",
    "device_spec_patch",
    "physical_edge_patch",
    "process_patch",
    "signal_patch",
    "scene_behavior_graph_patch",
    "parameter_binding_patch",
    "diagnostic_report",
    "question_set",
    "scenario_experiment_plan",
]

ARTIFACT_TYPES: set[str] = set(ArtifactType.__args__)
PATCH_ARTIFACT_TYPES: set[str] = {
    "scene_patch",
    "device_spec_patch",
    "physical_edge_patch",
    "process_patch",
    "signal_patch",
    "scene_behavior_graph_patch",
    "parameter_binding_patch",
}

AGENT_EVENT_TYPES: set[str] = {
    "agent.run_created",
    "agent.scene_loaded",
    "agent.device_specs_loaded",
    "agent.topology_loaded",
    "agent.topology_built",
    "agent.intent_parsed",
    "agent.slots_resolved",
    "agent.parameters_extracted",
    "agent.process_draft_created",
    "agent.signal_plan_created",
    "agent.behavior_graph_created",
    "agent.validation_failed",
    "agent.validation_passed",
    "agent.validation_repaired",
    "agent.waiting_for_user_review",
    "agent.patch_staged",
    "agent.patch_applied",
    "agent.runtime_observation_diagnosed",
    "agent.scenario_plan_created",
    "agent.finalized",
    "agent.cancelled",
}


class ValidationIssue(BaseModel):
    severity: Literal["blocking", "warning", "info"]
    code: str
    message: str
    path: str | None = None
    details: JsonDict = Field(default_factory=dict)


class ValidationReport(BaseModel):
    valid: bool = True
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: JsonDict = Field(default_factory=dict)

    @classmethod
    def from_issues(cls, issues: list[ValidationIssue | JsonDict], summary: JsonDict | None = None) -> "ValidationReport":
        normalized = [issue if isinstance(issue, ValidationIssue) else ValidationIssue(**issue) for issue in issues]
        return cls(valid=not any(issue.severity == "blocking" for issue in normalized), issues=normalized, summary=summary or {})

    def as_dict(self) -> JsonDict:
        return self.model_dump(mode="json")


class PatchOperation(BaseModel):
    op: Literal["add", "replace", "remove", "test"]
    path: str = Field(min_length=1)
    value: Any = None


class PatchEnvelope(BaseModel):
    patch_id: str = Field(default_factory=lambda: new_id("patch"))
    artifact_type: ArtifactType
    base_scene_revision: int = Field(ge=0)
    target_revision_policy: Literal["exact", "latest_after_revalidate"] = "exact"
    operations: list[PatchOperation] = Field(default_factory=list)
    reason: str = Field(min_length=1)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    validation_before: ValidationReport | None = None
    validation_after: ValidationReport | None = None
    approval_required: bool = True
    rollback_hint: str | None = None
    source_trace: list[JsonDict] = Field(default_factory=list)
    risk: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def artifact_type_must_be_patch(self) -> "PatchEnvelope":
        if self.artifact_type not in PATCH_ARTIFACT_TYPES:
            raise ValueError(f"PatchEnvelope cannot use non-patch artifact type: {self.artifact_type}")
        if not self.operations:
            raise ValueError("PatchEnvelope.operations must contain at least one operation")
        return self


class AgentArtifactContract(BaseModel):
    artifact_id: str = Field(default_factory=lambda: new_id("artifact"))
    artifact_type: ArtifactType
    base_scene_revision: int = Field(ge=0)
    payload: JsonDict
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    approval_required: bool = True
    validation_report: ValidationReport = Field(default_factory=ValidationReport)
    source_trace: list[JsonDict] = Field(default_factory=list)


class AgentState(BaseModel):
    run_id: str
    project_id: str
    scene_id: str
    user_message: str
    base_scene_revision: int
    scene: JsonDict | None = None
    device_specs: dict[str, JsonDict] = Field(default_factory=dict)
    topology: JsonDict | None = None
    intent: JsonDict = Field(default_factory=dict)
    resolved_slots: JsonDict = Field(default_factory=dict)
    candidate_artifacts: list[AgentArtifactContract] = Field(default_factory=list)
    validation: ValidationReport | None = None
    runtime_snapshot: JsonDict | None = None
    final_response: JsonDict | None = None
    repair_attempts: int = 0
    cancelled: bool = False


class SchemaContractRegistry:
    """Central registry for Agent-side input/output contracts."""

    _contracts: ClassVar[dict[str, type[BaseModel]]] = {
        "AgentState": AgentState,
        "AgentArtifact": AgentArtifactContract,
        "PatchEnvelope": PatchEnvelope,
        "ValidationReport": ValidationReport,
    }

    def register(self, name: str, model: type[BaseModel]) -> None:
        self._contracts[name] = model

    def get(self, name: str) -> type[BaseModel] | None:
        return self._contracts.get(name)

    def list_contracts(self) -> list[str]:
        return sorted(self._contracts)

    def validate(self, name: str, payload: JsonDict) -> ValidationReport:
        model = self.get(name)
        if not model:
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "UNKNOWN_SCHEMA_CONTRACT",
                        "message": f"Schema contract is not registered: {name}",
                    }
                ]
            )
        try:
            model.model_validate(payload)
        except Exception as exc:  # Pydantic reports are already structured but too verbose for API payloads.
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "SCHEMA_CONTRACT_VALIDATION_FAILED",
                        "message": str(exc),
                    }
                ]
            )
        return ValidationReport(summary={"contract": name})


class ArtifactSchemaValidator:
    """Validate candidate artifact envelopes before they can be persisted or applied."""

    def validate_payload(self, artifact_type: str, payload: JsonDict) -> ValidationReport:
        if artifact_type not in ARTIFACT_TYPES:
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "UNKNOWN_ARTIFACT_TYPE",
                        "message": f"Unsupported artifact type: {artifact_type}",
                        "path": "artifact_type",
                    }
                ]
            )
        if artifact_type in PATCH_ARTIFACT_TYPES:
            return self._validate_patch_payload(artifact_type, payload)
        if artifact_type == "diagnostic_report":
            return self._require_fields(artifact_type, payload, ["symptom", "root_causes", "evidence", "suggested_repairs", "can_auto_repair"])
        if artifact_type == "question_set":
            return self._require_fields(artifact_type, payload, ["questions"])
        if artifact_type == "scenario_experiment_plan":
            return self._require_fields(artifact_type, payload, ["variants", "metrics", "recommendation_policy"])
        return ValidationReport(summary={"artifact_type": artifact_type})

    def validate_artifact(self, artifact: AgentArtifactContract | JsonDict) -> ValidationReport:
        try:
            normalized = artifact if isinstance(artifact, AgentArtifactContract) else AgentArtifactContract.model_validate(artifact)
        except Exception as exc:
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "ARTIFACT_CONTRACT_INVALID",
                        "message": str(exc),
                    }
                ]
            )
        payload_report = self.validate_payload(normalized.artifact_type, normalized.payload)
        if not payload_report.valid:
            return payload_report
        return ValidationReport(summary={"artifact_type": normalized.artifact_type, **payload_report.summary})

    @staticmethod
    def _validate_patch_payload(artifact_type: str, payload: JsonDict) -> ValidationReport:
        try:
            envelope = PatchEnvelope.model_validate(payload)
        except Exception as exc:
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "PATCH_ENVELOPE_INVALID",
                        "message": str(exc),
                    }
                ]
            )
        if envelope.artifact_type != artifact_type:
            return ValidationReport.from_issues(
                [
                    {
                        "severity": "blocking",
                        "code": "PATCH_ARTIFACT_TYPE_MISMATCH",
                        "message": f"Patch payload declares {envelope.artifact_type}, artifact declares {artifact_type}.",
                        "path": "payload.artifact_type",
                    }
                ]
            )
        return ValidationReport(summary={"artifact_type": artifact_type, "operation_count": len(envelope.operations)})

    @staticmethod
    def _require_fields(artifact_type: str, payload: JsonDict, fields: list[str]) -> ValidationReport:
        issues = [
            {
                "severity": "blocking",
                "code": "ARTIFACT_FIELD_MISSING",
                "message": f"{artifact_type} is missing required field: {field}",
                "path": field,
            }
            for field in fields
            if field not in payload
        ]
        return ValidationReport.from_issues(issues, {"artifact_type": artifact_type})
