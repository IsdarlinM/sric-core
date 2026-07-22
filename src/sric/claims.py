from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ClaimStatus, Confidence


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ValidationRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: ClaimStatus
    timestamp: datetime = Field(default_factory=utcnow)
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str
    validator: str = "human"
    deterministic: bool = False


class TemporalValidity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)


class ClaimContract(BaseModel):
    """Claim-Evidence Contract v2.

    Claims preserve uncertainty. A VALIDATED state is only legal with deterministic
    validation evidence. UNKNOWN is a first-class result and never means safe.
    """

    model_config = ConfigDict(extra="forbid")
    claim_id: str
    claim_type: str
    statement: str
    status: ClaimStatus
    confidence: Confidence
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    validation_requirements: list[str] = Field(default_factory=list)
    source_independence: float = Field(default=0.0, ge=0.0, le=1.0)
    temporal_validity: TemporalValidity = Field(default_factory=TemporalValidity)
    validation_history: list[ValidationRecord] = Field(default_factory=list)
    source: str
    inference_method: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence_rules(self) -> "ClaimContract":
        if self.status is ClaimStatus.OBSERVED and not self.evidence_ids:
            raise ValueError("OBSERVED claims require direct evidence")
        if self.status is ClaimStatus.INFERRED and not self.inference_method:
            raise ValueError("INFERRED claims require an explainable inference_method")
        if self.status is ClaimStatus.HYPOTHESIS and not self.validation_requirements:
            raise ValueError("HYPOTHESIS claims require validation_requirements")
        if self.status is ClaimStatus.VALIDATED:
            if not self.evidence_ids:
                raise ValueError("VALIDATED claims require evidence")
            if not any(x.status is ClaimStatus.VALIDATED and x.deterministic and x.evidence_ids for x in self.validation_history):
                raise ValueError("VALIDATED claims require deterministic validation history")
        if self.status is ClaimStatus.REJECTED and not self.counter_evidence_ids and not self.validation_history:
            raise ValueError("REJECTED claims require counter-evidence or rejection history")
        return self


_ALLOWED: dict[ClaimStatus, set[ClaimStatus]] = {
    ClaimStatus.UNKNOWN: {ClaimStatus.OBSERVED, ClaimStatus.INFERRED, ClaimStatus.HYPOTHESIS, ClaimStatus.REJECTED},
    ClaimStatus.OBSERVED: {ClaimStatus.INFERRED, ClaimStatus.HYPOTHESIS, ClaimStatus.REJECTED},
    ClaimStatus.INFERRED: {ClaimStatus.HYPOTHESIS, ClaimStatus.REJECTED, ClaimStatus.UNKNOWN},
    ClaimStatus.HYPOTHESIS: {ClaimStatus.VALIDATED, ClaimStatus.REJECTED, ClaimStatus.UNKNOWN},
    ClaimStatus.VALIDATED: {ClaimStatus.REJECTED},
    ClaimStatus.REJECTED: {ClaimStatus.HYPOTHESIS, ClaimStatus.UNKNOWN},
}


def transition_claim(
    claim: ClaimContract,
    new_status: ClaimStatus,
    *,
    reason: str,
    evidence_ids: list[str] | None = None,
    deterministic: bool = False,
    validator: str = "human",
) -> ClaimContract:
    if new_status is claim.status:
        return claim
    if new_status not in _ALLOWED[claim.status]:
        raise ValueError(f"illegal claim transition {claim.status} -> {new_status}")
    supplied = list(evidence_ids or [])
    if new_status is ClaimStatus.VALIDATED and (not deterministic or not supplied):
        raise ValueError("VALIDATED transition requires deterministic evidence")
    history = list(claim.validation_history)
    history.append(ValidationRecord(status=new_status, evidence_ids=supplied, reason=reason, validator=validator, deterministic=deterministic))
    evidence = list(dict.fromkeys([*claim.evidence_ids, *supplied]))
    counter = claim.counter_evidence_ids
    if new_status is ClaimStatus.REJECTED:
        counter = list(dict.fromkeys([*counter, *supplied]))
    return claim.model_copy(update={"status":new_status,"evidence_ids":evidence,"counter_evidence_ids":counter,"validation_history":history,"updated_at":utcnow()})
