from datetime import datetime, timedelta, timezone

import pytest

from sric.bitemporal import (
    BitemporalBounds,
    BitemporalRecord,
    detect_temporal_conflicts,
    select_bitemporal,
    supersede_record,
)
from sric.models import ClaimStatus


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
T1 = T0 + timedelta(days=10)
T2 = T1 + timedelta(days=10)
T3 = T2 + timedelta(days=10)


def record(
    record_id: str,
    value: object,
    *,
    valid_from: datetime = T0,
    valid_to: datetime | None = None,
    recorded_at: datetime = T1,
) -> BitemporalRecord:
    return BitemporalRecord(
        record_id=record_id,
        entity_id="asset-1",
        fact_type="owner",
        value=value,
        status=ClaimStatus.OBSERVED,
        source_id="source",
        evidence_ids=[f"E-{record_id}"],
        bounds=BitemporalBounds(
            valid_from=valid_from,
            valid_to=valid_to,
            recorded_at=recorded_at,
        ),
    )


def test_valid_time_and_knowledge_time_are_distinct() -> None:
    item = record("R-1", "org-a", valid_from=T0, recorded_at=T2)
    assert item.bounds.valid_at(T1) is True
    assert item.bounds.known_at(T1) is False
    assert item.visible_at(valid_at=T1, known_at=T3) is True


def test_query_does_not_use_future_knowledge() -> None:
    old = record("R-OLD", "org-a", recorded_at=T1)
    new = record("R-NEW", "org-b", recorded_at=T3)
    selected = select_bitemporal([old, new], valid_at=T2, known_at=T2)
    assert [item.record_id for item in selected] == ["R-OLD"]


def test_superseded_record_disappears_from_later_knowledge_view() -> None:
    old = supersede_record(record("R-OLD", "org-a"), superseded_at=T2)
    assert old.bounds.known_at(T1) is True
    assert old.bounds.known_at(T3) is False


def test_conflicting_visible_facts_are_reported() -> None:
    conflicts = detect_temporal_conflicts(
        [record("R-1", "org-a"), record("R-2", "org-b")],
        valid_at=T2,
        known_at=T2,
    )
    assert len(conflicts) == 1
    assert conflicts[0].record_ids == ["R-1", "R-2"]
    assert "remain UNKNOWN" in conflicts[0].reason


def test_semantically_equal_json_values_do_not_conflict_by_key_order() -> None:
    conflicts = detect_temporal_conflicts(
        [record("R-1", {"a": 1, "b": 2}), record("R-2", {"b": 2, "a": 1})],
        valid_at=T2,
        known_at=T2,
    )
    assert conflicts == []


def test_non_overlapping_validity_does_not_conflict() -> None:
    conflicts = detect_temporal_conflicts(
        [
            record("R-1", "org-a", valid_from=T0, valid_to=T1),
            record("R-2", "org-b", valid_from=T1),
        ],
        valid_at=T2,
        known_at=T2,
    )
    assert conflicts == []


def test_observed_records_require_evidence() -> None:
    with pytest.raises(ValueError, match="require evidence_ids"):
        BitemporalRecord(
            record_id="R-X",
            entity_id="asset-1",
            fact_type="owner",
            value="org-a",
            status=ClaimStatus.OBSERVED,
            source_id="source",
            bounds=BitemporalBounds(valid_from=T0, recorded_at=T1),
        )


def test_naive_datetimes_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        BitemporalBounds(valid_from=datetime(2026, 1, 1), recorded_at=T1)
