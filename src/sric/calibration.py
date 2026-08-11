from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import fsum
from typing import Iterable, Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SkepticVerdict(str, Enum):
    RETAIN = "RETAIN"
    REDUCE = "REDUCE"
    REJECT = "REJECT"
    UNKNOWN = "UNKNOWN"


class ConfidenceSignal(BaseModel):
    """One explainable contribution to a candidate conclusion.

    ``source_group`` identifies a shared upstream origin. Signals from the same
    group are capped together so mirrors, derived feeds and copied documents do
    not masquerade as independent confirmation.
    """

    model_config = ConfigDict(extra="forbid")

    signal: str
    contribution: float = Field(ge=-1.0, le=1.0)
    reason: str
    source_id: str
    source_group: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime | None = None
    direct_observation: bool = False
    source_quality: float = Field(default=0.5, ge=0.0, le=1.0)
    specificity: float = Field(default=0.5, ge=0.0, le=1.0)
    temporal_half_life_days: int = Field(default=365, ge=1, le=36500)

    @model_validator(mode="after")
    def require_evidence_for_direct_observation(self) -> "ConfidenceSignal":
        if self.direct_observation and not self.evidence_ids:
            raise ValueError("direct observations require evidence_ids")
        return self

    def temporal_relevance(self, *, at: datetime | None = None) -> float:
        reference = at or utcnow()
        observed = self.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        if self.expires_at is not None:
            expires = self.expires_at
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires <= reference:
                return 0.0
        age_days = max(0.0, (reference - observed).total_seconds() / 86400.0)
        return float(0.5 ** (age_days / self.temporal_half_life_days))

    def effective_contribution(self, *, at: datetime | None = None) -> float:
        direct_factor = 1.0 if self.direct_observation else 0.85
        return (
            self.contribution
            * self.source_quality
            * self.specificity
            * self.temporal_relevance(at=at)
            * direct_factor
        )


class ConfidenceBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)
    base_confidence: float = Field(ge=0.0, le=1.0)
    source_independence: float = Field(ge=0.0, le=1.0)
    temporal_relevance: float = Field(ge=0.0, le=1.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    positive_contribution: float
    negative_contribution: float
    contributing_signal_ids: list[str] = Field(default_factory=list)
    duplicate_source_groups: list[str] = Field(default_factory=list)
    missing_required_evidence: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)


class SkepticReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: SkepticVerdict
    adjusted_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    alternative_explanations: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    missing_required_evidence: list[str] = Field(default_factory=list)


def _grouped_effective_contributions(
    signals: Iterable[ConfidenceSignal], *, at: datetime
) -> tuple[list[float], list[str], list[str]]:
    grouped: dict[str, list[tuple[ConfidenceSignal, float]]] = {}
    signal_ids: list[str] = []
    for item in signals:
        group = item.source_group or item.source_id
        grouped.setdefault(group, []).append((item, item.effective_contribution(at=at)))
        signal_ids.append(item.signal)

    effective: list[float] = []
    duplicates: list[str] = []
    for group, values in grouped.items():
        if len(values) > 1:
            duplicates.append(group)
        positives = [value for _, value in values if value >= 0]
        negatives = [value for _, value in values if value < 0]
        if positives:
            effective.append(max(positives))
        if negatives:
            effective.append(min(negatives))
    return effective, sorted(signal_ids), sorted(duplicates)


def score_confidence(
    signals: Sequence[ConfidenceSignal],
    *,
    base_confidence: float = 0.1,
    required_evidence: Sequence[str] = (),
    at: datetime | None = None,
    maximum: float = 0.95,
) -> ConfidenceBreakdown:
    """Produce a conservative, explainable advisory confidence score.

    This function never validates a finding. It discounts derived and stale
    observations and prevents duplicate upstream sources from inflating the
    result.
    """

    if not 0.0 <= base_confidence <= 1.0:
        raise ValueError("base_confidence must be between 0 and 1")
    if not 0.0 < maximum <= 1.0:
        raise ValueError("maximum must be greater than 0 and at most 1")

    reference = at or utcnow()
    available_evidence = {evidence_id for signal in signals for evidence_id in signal.evidence_ids}
    missing = sorted(set(required_evidence) - available_evidence)
    completeness = (
        1.0
        if not required_evidence
        else (len(required_evidence) - len(missing)) / len(required_evidence)
    )

    values, signal_ids, duplicates = _grouped_effective_contributions(signals, at=reference)
    positive = fsum(value for value in values if value > 0)
    negative = fsum(value for value in values if value < 0)
    groups = {signal.source_group or signal.source_id for signal in signals}
    source_ids = {signal.source_id for signal in signals}
    independence = 0.0 if not source_ids else min(1.0, len(groups) / len(source_ids))
    temporal = (
        0.0
        if not signals
        else fsum(signal.temporal_relevance(at=reference) for signal in signals) / len(signals)
    )

    missing_penalty = 0.35 * (1.0 - completeness)
    raw = base_confidence + positive + negative - missing_penalty
    confidence = min(maximum, max(0.0, raw))

    explanation = [
        f"Independent source groups: {len(groups)} of {len(source_ids)} source IDs.",
        f"Average temporal relevance: {temporal:.4f}.",
        f"Required evidence completeness: {completeness:.4f}.",
    ]
    if duplicates:
        explanation.append("Duplicate upstream groups were capped: " + ", ".join(duplicates) + ".")
    if missing:
        explanation.append("Missing required evidence: " + ", ".join(missing) + ".")
    explanation.append("Confidence is advisory and cannot create a VALIDATED finding.")

    return ConfidenceBreakdown(
        confidence=round(confidence, 6),
        base_confidence=base_confidence,
        source_independence=round(independence, 6),
        temporal_relevance=round(temporal, 6),
        evidence_completeness=round(completeness, 6),
        positive_contribution=round(positive, 6),
        negative_contribution=round(negative, 6),
        contributing_signal_ids=signal_ids,
        duplicate_source_groups=duplicates,
        missing_required_evidence=missing,
        explanation=explanation,
    )


def skeptic_review(
    breakdown: ConfidenceBreakdown,
    *,
    alternative_explanations: Sequence[str] = (),
    counter_evidence_ids: Sequence[str] = (),
    missing_required_evidence: Sequence[str] = (),
) -> SkepticReview:
    """Attempt to refute or weaken a candidate before human validation."""

    missing = sorted(set(breakdown.missing_required_evidence) | set(missing_required_evidence))
    counter = sorted(set(counter_evidence_ids))
    alternatives = sorted(set(alternative_explanations))

    adjusted = breakdown.confidence
    reasons: list[str] = []
    if counter:
        adjusted -= min(0.6, 0.15 * len(counter))
        reasons.append(f"{len(counter)} counter-evidence item(s) reduce confidence.")
    if alternatives:
        adjusted -= min(0.3, 0.05 * len(alternatives))
        reasons.append(f"{len(alternatives)} plausible alternative explanation(s) remain unresolved.")
    if missing:
        adjusted = min(adjusted, 0.49)
        reasons.append("Required evidence is missing; validation must abstain.")
    adjusted = min(0.95, max(0.0, adjusted))

    if counter and adjusted < 0.2:
        verdict = SkepticVerdict.REJECT
    elif missing:
        verdict = SkepticVerdict.UNKNOWN
    elif adjusted < breakdown.confidence:
        verdict = SkepticVerdict.REDUCE
    else:
        verdict = SkepticVerdict.RETAIN
        reasons.append("No refuting evidence or unresolved alternative explanation was supplied.")

    return SkepticReview(
        verdict=verdict,
        adjusted_confidence=round(adjusted, 6),
        reasons=reasons,
        alternative_explanations=alternatives,
        counter_evidence_ids=counter,
        missing_required_evidence=missing,
    )


def brier_score(predictions: Sequence[float], outcomes: Sequence[bool | int]) -> float:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        raise ValueError("at least one prediction is required")
    if any(not 0.0 <= value <= 1.0 for value in predictions):
        raise ValueError("predictions must be between 0 and 1")
    return round(
        fsum(
            (prediction - float(bool(outcome))) ** 2
            for prediction, outcome in zip(predictions, outcomes)
        )
        / len(predictions),
        8,
    )


def expected_calibration_error(
    predictions: Sequence[float], outcomes: Sequence[bool | int], *, bins: int = 10
) -> float:
    if len(predictions) != len(outcomes):
        raise ValueError("predictions and outcomes must have equal length")
    if not predictions:
        raise ValueError("at least one prediction is required")
    if bins < 2 or bins > 100:
        raise ValueError("bins must be between 2 and 100")
    if any(not 0.0 <= value <= 1.0 for value in predictions):
        raise ValueError("predictions must be between 0 and 1")

    total = len(predictions)
    error = 0.0
    for index in range(bins):
        lower = index / bins
        upper = (index + 1) / bins
        members = [
            (prediction, float(bool(outcome)))
            for prediction, outcome in zip(predictions, outcomes)
            if lower <= prediction < upper or (index == bins - 1 and prediction == 1.0)
        ]
        if not members:
            continue
        mean_prediction = fsum(item[0] for item in members) / len(members)
        mean_outcome = fsum(item[1] for item in members) / len(members)
        error += len(members) / total * abs(mean_prediction - mean_outcome)
    return round(error, 8)
