from datetime import datetime, timedelta, timezone

import pytest

from sric.calibration import (
    ConfidenceSignal,
    SkepticVerdict,
    brier_score,
    expected_calibration_error,
    score_confidence,
    skeptic_review,
)


NOW = datetime(2026, 8, 6, tzinfo=timezone.utc)


def signal(
    name: str,
    *,
    source: str,
    group: str,
    contribution: float = 0.5,
    evidence: str = "E-1",
    observed_at: datetime = NOW,
) -> ConfidenceSignal:
    return ConfidenceSignal(
        signal=name,
        contribution=contribution,
        reason="test signal",
        source_id=source,
        source_group=group,
        evidence_ids=[evidence],
        direct_observation=True,
        source_quality=1.0,
        specificity=1.0,
        observed_at=observed_at,
    )


def test_duplicate_upstream_sources_do_not_stack() -> None:
    result = score_confidence(
        [
            signal("dns-a", source="feed-a", group="same-upstream", evidence="E-1"),
            signal("dns-b", source="feed-b", group="same-upstream", evidence="E-2"),
        ],
        base_confidence=0.1,
        at=NOW,
    )

    assert result.confidence == 0.6
    assert result.source_independence == 0.5
    assert result.duplicate_source_groups == ["same-upstream"]


def test_stale_signal_is_discounted() -> None:
    fresh = signal("fresh", source="fresh", group="fresh")
    stale = signal(
        "stale",
        source="stale",
        group="stale",
        observed_at=NOW - timedelta(days=365),
    )
    stale.temporal_half_life_days = 365

    fresh_result = score_confidence([fresh], at=NOW)
    stale_result = score_confidence([stale], at=NOW)

    assert stale_result.confidence < fresh_result.confidence
    assert stale_result.temporal_relevance == 0.5


def test_missing_required_evidence_forces_skeptic_abstention() -> None:
    breakdown = score_confidence(
        [signal("direct", source="one", group="one")],
        required_evidence=["E-1", "E-MISSING"],
        at=NOW,
    )
    review = skeptic_review(breakdown)

    assert review.verdict is SkepticVerdict.UNKNOWN
    assert review.adjusted_confidence <= 0.49
    assert review.missing_required_evidence == ["E-MISSING"]


def test_counterevidence_can_reject_candidate() -> None:
    breakdown = score_confidence([], base_confidence=0.2, at=NOW)
    review = skeptic_review(
        breakdown,
        counter_evidence_ids=["CE-1", "CE-2"],
    )

    assert review.verdict is SkepticVerdict.REJECT
    assert review.adjusted_confidence == 0.0


def test_calibration_metrics() -> None:
    assert brier_score([0.8, 0.2], [1, 0]) == 0.04
    assert expected_calibration_error([0.8, 0.2], [1, 0], bins=5) == 0.2


def test_direct_observation_requires_evidence() -> None:
    with pytest.raises(ValueError, match="direct observations require evidence_ids"):
        ConfidenceSignal(
            signal="invalid",
            contribution=0.2,
            reason="missing evidence",
            source_id="source",
            direct_observation=True,
        )
