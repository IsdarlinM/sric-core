from __future__ import annotations

from hypothesis import given, strategies as st
from pydantic import ValidationError

from sric.cases import claim_fingerprint
from sric.correlation import CorrelationResult


_text = st.text(
    alphabet=st.characters(
        blacklist_categories=("Cs",),
        blacklist_characters=("\x00",),
    ),
    min_size=1,
    max_size=48,
)


@given(_text, _text, _text, _text, st.dictionaries(_text, _text, max_size=8))
def test_claim_fingerprint_is_deterministic_for_generated_inputs(
    claim_type: str,
    subject: str,
    predicate: str,
    object_value: str,
    context: dict[str, str],
) -> None:
    first = claim_fingerprint(
        claim_type=claim_type,
        subject=subject,
        predicate=predicate,
        object_value=object_value,
        context=context,
    )
    second = claim_fingerprint(
        claim_type=claim_type,
        subject=subject,
        predicate=predicate,
        object_value=object_value,
        context=context,
    )
    assert first == second
    assert first.startswith("claim:")


@given(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False))
def test_generated_correlation_result_cannot_accept_validated(confidence: float) -> None:
    try:
        CorrelationResult(
            rule_id="generated",
            title="generated",
            status="VALIDATED",
            confidence=confidence,
            fact_ids=["fact-1"],
        )
    except ValidationError:
        return
    raise AssertionError("automated correlation accepted VALIDATED")
