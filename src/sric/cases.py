from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ActionClass, ClaimStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CaseMaturity(StrEnum):
    NEW = "NEW"
    TRIAGED = "TRIAGED"
    VALIDATION_READY = "VALIDATION_READY"
    REPORT_READY = "REPORT_READY"
    CLOSED = "CLOSED"


class CaseArtifactType(StrEnum):
    OBSERVATION = "OBSERVATION"
    CLAIM = "CLAIM"
    HYPOTHESIS = "HYPOTHESIS"
    EVIDENCE = "EVIDENCE"
    COUNTER_EVIDENCE = "COUNTER_EVIDENCE"
    MODEL = "MODEL"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    FINDING = "FINDING"


class CaseArtifact(BaseModel):
    """One evidence-linked research artifact shared across Sentinel Forge products."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str
    artifact_type: CaseArtifactType
    source_tool: str
    source_ref: str
    status: ClaimStatus = ClaimStatus.UNKNOWN
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validated_requires_evidence(self) -> "CaseArtifact":
        if self.status is ClaimStatus.VALIDATED and not self.evidence_ids:
            raise ValueError("VALIDATED case artifacts require evidence_ids")
        return self


class ValidationRecipe(BaseModel):
    """A proposed deterministic validation step; execution still requires policy gates."""

    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    artifact_id: str
    action_class: ActionClass
    target: str
    method: str
    deterministic_success: str
    required_evidence: list[str] = Field(default_factory=list)
    scope_snapshot_id: str | None = None
    policy_decision_id: str | None = None
    human_approval_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def enforce_operational_safety(self) -> "ValidationRecipe":
        if self.action_class is ActionClass.PROHIBITED:
            raise ValueError("PROHIBITED actions cannot be represented as validation recipes")
        if self.action_class is ActionClass.OUT_OF_SCOPE:
            raise ValueError("OUT_OF_SCOPE actions cannot be represented as validation recipes")
        if self.action_class in {
            ActionClass.MUTATING_REVERSIBLE,
            ActionClass.MUTATING_DESTRUCTIVE,
        } and not self.human_approval_required:
            raise ValueError("mutating validation recipes require human approval")
        return self


class SentinelCase(BaseModel):
    """Cross-product investigation container.

    A case groups observations, hypotheses, counter-evidence and validation plans without
    changing the truth state of any artifact. VALIDATED remains evidence-gated.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str
    title: str
    maturity: CaseMaturity = CaseMaturity.NEW
    artifacts: list[CaseArtifact] = Field(default_factory=list)
    validation_recipes: list[ValidationRecipe] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_unique_ids(self) -> "SentinelCase":
        artifact_ids = [item.artifact_id for item in self.artifacts]
        recipe_ids = [item.recipe_id for item in self.validation_recipes]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("case artifact_id values must be unique")
        if len(recipe_ids) != len(set(recipe_ids)):
            raise ValueError("validation recipe_id values must be unique")
        known = set(artifact_ids)
        dangling = sorted(
            recipe.artifact_id
            for recipe in self.validation_recipes
            if recipe.artifact_id not in known
        )
        if dangling:
            raise ValueError("validation recipes reference unknown artifacts: " + ", ".join(dangling))
        return self

    def evidence_ids(self) -> list[str]:
        return sorted({value for item in self.artifacts for value in item.evidence_ids})

    def counter_evidence_ids(self) -> list[str]:
        return sorted({value for item in self.artifacts for value in item.counter_evidence_ids})

    def unresolved_artifacts(self) -> list[str]:
        return sorted(
            item.artifact_id
            for item in self.artifacts
            if item.status in {ClaimStatus.UNKNOWN, ClaimStatus.HYPOTHESIS, ClaimStatus.INFERRED}
        )


def claim_fingerprint(
    *,
    claim_type: str,
    subject: str,
    predicate: str,
    object_value: str,
    context: dict[str, Any] | None = None,
) -> str:
    """Create a deterministic cross-tool fingerprint for semantically identical claims."""

    payload = {
        "claim_type": claim_type.strip().casefold(),
        "subject": subject.strip(),
        "predicate": predicate.strip().casefold(),
        "object": object_value.strip(),
        "context": context or {},
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "claim:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def evidence_adequacy(
    artifacts: Sequence[CaseArtifact], required_evidence: Sequence[str]
) -> float:
    """Measure required-evidence coverage without promoting a claim state."""

    required = set(required_evidence)
    if not required:
        return 1.0
    available = {value for item in artifacts for value in item.evidence_ids}
    return round(len(required & available) / len(required), 6)
