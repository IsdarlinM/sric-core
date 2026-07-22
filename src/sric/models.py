from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ClaimStatus(StrEnum):
    OBSERVED = "OBSERVED"
    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class FindingStatus(StrEnum):
    UNTRIAGED = "UNTRIAGED"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    LIKELY_FALSE_POSITIVE = "LIKELY_FALSE_POSITIVE"
    VALIDATION_READY = "VALIDATION_READY"
    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"


class ProvenanceType(StrEnum):
    DIRECT_OBSERVATION = "direct_observation"
    IMPORTED = "imported"
    PUBLIC_SOURCE = "public_source"
    USER_INPUT = "user_input"
    TOOL_DERIVED = "tool_derived"
    AI_INFERRED = "ai_inferred"
    VALIDATED = "validated"


class ActionClass(StrEnum):
    READ_ONLY_SAFE = "READ_ONLY_SAFE"
    READ_ONLY_SENSITIVE = "READ_ONLY_SENSITIVE"
    MUTATING_REVERSIBLE = "MUTATING_REVERSIBLE"
    MUTATING_DESTRUCTIVE = "MUTATING_DESTRUCTIVE"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    PROHIBITED = "PROHIBITED"


class OperationMode(StrEnum):
    PASSIVE = "PASSIVE"
    OBSERVE = "OBSERVE"
    VALIDATE = "VALIDATE"
    LAB = "LAB"


class Confidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: float = Field(ge=0.0, le=1.0)
    source_count: int = Field(default=0, ge=0)
    source_independence: float = Field(default=0.0, ge=0.0, le=1.0)
    recency: float = Field(default=0.0, ge=0.0, le=1.0)
    directness: float = Field(default=0.0, ge=0.0, le=1.0)
    consistency: float = Field(default=0.0, ge=0.0, le=1.0)
    rationale: str = ""


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provenance_type: ProvenanceType
    source: str
    method: str
    tool_version: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    parent_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    media_type: str
    size_bytes: int = Field(ge=0)
    created_at: datetime = Field(default_factory=utcnow)
    provenance: Provenance
    redacted: bool = False


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    human_id: str
    entity_type: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    source: str
    confidence: Confidence
    provenance: Provenance
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    schema_version: str = "1.0"


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    evidence: list[EvidenceReference] = Field(default_factory=list)
    confidence: Confidence
    discovery_method: str
    schema_version: str = "1.0"


class Claim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_id: str
    claim: str
    status: ClaimStatus
    confidence: Confidence
    evidence_ids: list[str]
    counter_evidence_ids: list[str] = Field(default_factory=list)
    source: str
    inference_method: str | None = None
    timestamp: datetime = Field(default_factory=utcnow)
    validation_status: FindingStatus = FindingStatus.NEEDS_EVIDENCE
    limitations: list[str] = Field(default_factory=list)
    generated_by: dict[str, str] = Field(default_factory=dict)

    @field_validator("evidence_ids")
    @classmethod
    def validated_claims_need_evidence(cls, value: list[str], info: Any) -> list[str]:
        status = info.data.get("status")
        if status == ClaimStatus.VALIDATED and not value:
            raise ValueError("VALIDATED claims require at least one evidence reference")
        return value


class ActionProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    actor: str
    method: str
    target: str
    action_class: ActionClass
    mode: OperationMode
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str
    allowed: bool
    decision: str
    matched_rule: str
    requires_approval: bool = False
    timestamp: datetime = Field(default_factory=utcnow)
