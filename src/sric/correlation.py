from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


class CorrelationFact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fact_id: str
    fact_type: str
    value: str
    source: str
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class CorrelationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_id: str
    title: str
    status: str = "HYPOTHESIS"
    confidence: float = Field(ge=0.0, le=1.0)
    fact_ids: list[str]
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence: list[str] = Field(default_factory=list)
    explanation: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class CorrelationRule:
    rule_id: str
    title: str
    evaluator: Callable[[list[CorrelationFact]], CorrelationResult | None]


class CorrelationEngine:
    """Deterministic explainable correlation registry; rules never directly validate findings."""

    def __init__(self) -> None:
        self._rules: dict[str, CorrelationRule] = {}

    def register(self, rule: CorrelationRule) -> None:
        if rule.rule_id in self._rules:
            raise ValueError(f"duplicate correlation rule: {rule.rule_id}")
        self._rules[rule.rule_id] = rule

    def evaluate(self, facts: list[CorrelationFact]) -> list[CorrelationResult]:
        results: list[CorrelationResult] = []
        for rule_id in sorted(self._rules):
            result = self._rules[rule_id].evaluator(facts)
            if result is not None:
                results.append(result)
        return results


def historical_active_relevance_rule() -> CorrelationRule:
    def evaluate(facts: list[CorrelationFact]) -> CorrelationResult | None:
        historical = [f for f in facts if f.fact_type == "historical_endpoint"]
        dns = [f for f in facts if f.fact_type == "current_dns"]
        auth = [f for f in facts if f.fact_type == "auth_observation"]
        if not historical or not dns:
            return None
        all_facts = historical + dns + auth
        sources = {f.source for f in all_facts}
        confidence = min(0.9, 0.45 + 0.12 * len(sources) + (0.12 if auth else 0.0))
        return CorrelationResult(
            rule_id="historical-active-relevance",
            title="Historical endpoint may retain current security relevance",
            confidence=confidence,
            fact_ids=[f.fact_id for f in all_facts],
            evidence_ids=sorted({e for f in all_facts for e in f.evidence_ids}),
            explanation=[
                "Historical endpoint evidence exists.",
                "Current DNS evidence exists.",
                "Authorization behavior is present." if auth else "Authorization relevance is UNKNOWN.",
            ],
        )

    return CorrelationRule(
        rule_id="historical-active-relevance",
        title="Historical endpoint may retain current security relevance",
        evaluator=evaluate,
    )
