from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class AutomatedCorrelationStatus(StrEnum):
    """Truth states that automated correlation is allowed to emit.

    VALIDATED is intentionally absent. Deterministic evidence-bearing validation is the
    only path to a validated finding.
    """

    INFERRED = "INFERRED"
    HYPOTHESIS = "HYPOTHESIS"


class CorrelationFact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fact_id: str
    fact_type: str
    value: str
    source: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_group: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class SignalContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    fact_ids: list[str]
    contribution: float = Field(ge=-1, le=1)
    reason: str


class CorrelationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    status: AutomatedCorrelationStatus = AutomatedCorrelationStatus.HYPOTHESIS
    confidence: float = Field(ge=0, le=1)
    fact_ids: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    contributions: list[SignalContribution] = Field(default_factory=list)
    source_independence: float = Field(default=0, ge=0, le=1)
    temporal_relevance: float = Field(default=1, ge=0, le=1)
    missing_evidence: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CorrelationRule:
    rule_id: str
    title: str
    evaluator: Callable[[list[CorrelationFact]], CorrelationResult | None]


class DeclarativeCorrelationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    title: str
    requires: list[str]
    optional: list[str] = Field(default_factory=list)
    base_confidence: float = Field(default=0.35, ge=0, le=1)
    per_independent_source: float = Field(default=0.08, ge=0, le=0.5)
    output_status: AutomatedCorrelationStatus = AutomatedCorrelationStatus.HYPOTHESIS

    def evaluate(self, facts: list[CorrelationFact]) -> CorrelationResult | None:
        by_type = {
            fact_type: [fact for fact in facts if fact.fact_type == fact_type]
            for fact_type in {*self.requires, *self.optional}
        }
        if any(not by_type.get(fact_type) for fact_type in self.requires):
            return None

        used = [
            fact
            for fact_type in self.requires + self.optional
            for fact in by_type.get(fact_type, [])
        ]
        groups = {fact.source_group or fact.source for fact in used}
        independence = min(1.0, len(groups) / max(1, len(used)))
        now = datetime.now(timezone.utc)
        ages: list[int] = []
        for fact in used:
            observed = (
                fact.observed_at
                if fact.observed_at.tzinfo
                else fact.observed_at.replace(tzinfo=timezone.utc)
            )
            ages.append(max(0, (now - observed).days))
        temporal = max(0.1, 1.0 - (sum(ages) / max(1, len(ages))) / 3650)
        counter = sorted({value for fact in used for value in fact.counter_evidence_ids})
        confidence = min(
            0.95,
            self.base_confidence
            + self.per_independent_source * len(groups)
            + 0.03 * sum(bool(by_type.get(fact_type)) for fact_type in self.optional),
        )
        confidence = max(0.05, confidence - 0.05 * len(counter)) * temporal
        contributions = [
            SignalContribution(
                signal=fact_type,
                fact_ids=[fact.fact_id for fact in by_type.get(fact_type, [])],
                contribution=0.1,
                reason=(
                    "required signal observed"
                    if fact_type in self.requires
                    else "optional signal observed"
                ),
            )
            for fact_type in self.requires + self.optional
            if by_type.get(fact_type)
        ]
        missing = [fact_type for fact_type in self.optional if not by_type.get(fact_type)]
        return CorrelationResult(
            rule_id=self.rule_id,
            title=self.title,
            status=self.output_status,
            confidence=round(confidence, 4),
            fact_ids=[fact.fact_id for fact in used],
            evidence_ids=sorted({value for fact in used for value in fact.evidence_ids}),
            counter_evidence=counter,
            contributions=contributions,
            source_independence=round(independence, 4),
            temporal_relevance=round(temporal, 4),
            missing_evidence=missing,
            explanation=[
                f"Independent source groups: {len(groups)}",
                f"Counter-evidence items: {len(counter)}",
                "Automated correlation can emit only INFERRED or HYPOTHESIS states.",
            ],
        )


class CorrelationEngine:
    def __init__(self) -> None:
        self._rules: dict[str, CorrelationRule | DeclarativeCorrelationRule] = {}

    def register(self, rule: CorrelationRule | DeclarativeCorrelationRule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"duplicate correlation rule: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def evaluate(self, facts: list[CorrelationFact]) -> list[CorrelationResult]:
        output: list[CorrelationResult] = []
        for rule_id in sorted(self._rules):
            rule = self._rules[rule_id]
            result = (
                rule.evaluate(facts)
                if isinstance(rule, DeclarativeCorrelationRule)
                else rule.evaluator(facts)
            )
            if result is not None:
                output.append(result)
        return output


def historical_active_relevance_rule() -> CorrelationRule:
    def evaluate(facts: list[CorrelationFact]) -> CorrelationResult | None:
        historical = [fact for fact in facts if fact.fact_type == "historical_endpoint"]
        dns = [fact for fact in facts if fact.fact_type == "current_dns"]
        auth = [fact for fact in facts if fact.fact_type == "auth_observation"]
        if not historical or not dns:
            return None
        all_facts = historical + dns + auth
        sources = {fact.source_group or fact.source for fact in all_facts}
        confidence = min(0.9, 0.45 + 0.12 * len(sources) + (0.12 if auth else 0))
        return CorrelationResult(
            rule_id="historical-active-relevance",
            title="Historical endpoint may retain current security relevance",
            confidence=confidence,
            fact_ids=[fact.fact_id for fact in all_facts],
            evidence_ids=sorted({value for fact in all_facts for value in fact.evidence_ids}),
            counter_evidence=sorted(
                {value for fact in all_facts for value in fact.counter_evidence_ids}
            ),
            source_independence=min(1, len(sources) / len(all_facts)),
            missing_evidence=[] if auth else ["auth_observation"],
            explanation=[
                "Historical endpoint evidence exists.",
                "Current DNS evidence exists.",
                "Authorization behavior is present."
                if auth
                else "Authorization relevance is UNKNOWN.",
            ],
        )

    return CorrelationRule(
        "historical-active-relevance",
        "Historical endpoint may retain current security relevance",
        evaluate,
    )
