from __future__ import annotations

import pytest
from pydantic import ValidationError

from sric.correlation import (
    AutomatedCorrelationStatus,
    CorrelationFact,
    CorrelationResult,
    DeclarativeCorrelationRule,
)


def test_declarative_correlation_emits_hypothesis() -> None:
    rule = DeclarativeCorrelationRule(rule_id="r1", title="candidate", requires=["dns"])
    result = rule.evaluate(
        [CorrelationFact(fact_id="f1", fact_type="dns", value="example.com", source="dns")]
    )
    assert result is not None
    assert result.status is AutomatedCorrelationStatus.HYPOTHESIS


def test_validated_is_not_an_automated_correlation_state() -> None:
    with pytest.raises(ValidationError):
        CorrelationResult(
            rule_id="r1",
            title="bad",
            status="VALIDATED",
            confidence=0.9,
            fact_ids=["f1"],
        )
