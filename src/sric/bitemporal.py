from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .models import ClaimStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value


class BitemporalBounds(BaseModel):
    """Separates when a fact is valid from when SRIC knew the fact."""

    model_config = ConfigDict(extra="forbid")

    valid_from: datetime
    valid_to: datetime | None = None
    recorded_at: datetime = Field(default_factory=utcnow)
    superseded_at: datetime | None = None

    @model_validator(mode="after")
    def validate_intervals(self) -> "BitemporalBounds":
        valid_from = _aware(self.valid_from, "valid_from")
        recorded_at = _aware(self.recorded_at, "recorded_at")
        if self.valid_to is not None:
            valid_to = _aware(self.valid_to, "valid_to")
            if valid_to <= valid_from:
                raise ValueError("valid_to must be later than valid_from")
        if self.superseded_at is not None:
            superseded = _aware(self.superseded_at, "superseded_at")
            if superseded <= recorded_at:
                raise ValueError("superseded_at must be later than recorded_at")
        return self

    def valid_at(self, moment: datetime) -> bool:
        moment = _aware(moment, "moment")
        return self.valid_from <= moment and (
            self.valid_to is None or moment < self.valid_to
        )

    def known_at(self, moment: datetime) -> bool:
        moment = _aware(moment, "moment")
        return self.recorded_at <= moment and (
            self.superseded_at is None or moment < self.superseded_at
        )


class BitemporalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    record_id: str
    entity_id: str
    fact_type: str
    value: Any
    status: ClaimStatus
    source_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    bounds: BitemporalBounds
    supersedes_record_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def evidence_semantics(self) -> "BitemporalRecord":
        if self.status in {ClaimStatus.OBSERVED, ClaimStatus.VALIDATED} and not self.evidence_ids:
            raise ValueError(f"{self.status} bitemporal records require evidence_ids")
        return self

    def visible_at(self, *, valid_at: datetime, known_at: datetime) -> bool:
        return self.bounds.valid_at(valid_at) and self.bounds.known_at(known_at)


class TemporalConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_id: str
    fact_type: str
    record_ids: list[str]
    reason: str


def select_bitemporal(
    records: Iterable[BitemporalRecord],
    *,
    valid_at: datetime,
    known_at: datetime,
    entity_id: str | None = None,
    fact_type: str | None = None,
) -> list[BitemporalRecord]:
    selected = [
        record
        for record in records
        if record.visible_at(valid_at=valid_at, known_at=known_at)
        and (entity_id is None or record.entity_id == entity_id)
        and (fact_type is None or record.fact_type == fact_type)
    ]
    return sorted(
        selected,
        key=lambda item: (
            item.entity_id,
            item.fact_type,
            item.bounds.recorded_at,
            item.record_id,
        ),
    )


def detect_temporal_conflicts(
    records: Iterable[BitemporalRecord],
    *,
    valid_at: datetime,
    known_at: datetime,
) -> list[TemporalConflict]:
    groups: dict[tuple[str, str], list[BitemporalRecord]] = {}
    for record in select_bitemporal(records, valid_at=valid_at, known_at=known_at):
        groups.setdefault((record.entity_id, record.fact_type), []).append(record)

    conflicts: list[TemporalConflict] = []
    for (entity_id, fact_type), values in groups.items():
        canonical_values = {repr(item.value) for item in values}
        if len(canonical_values) <= 1:
            continue
        conflicts.append(
            TemporalConflict(
                entity_id=entity_id,
                fact_type=fact_type,
                record_ids=sorted(item.record_id for item in values),
                reason=(
                    "Multiple simultaneously visible records contain different values; "
                    "the fact must remain UNKNOWN until reconciled."
                ),
            )
        )
    return sorted(conflicts, key=lambda item: (item.entity_id, item.fact_type))


def supersede_record(
    record: BitemporalRecord,
    *,
    superseded_at: datetime,
) -> BitemporalRecord:
    _aware(superseded_at, "superseded_at")
    bounds = record.bounds.model_copy(update={"superseded_at": superseded_at})
    return record.model_copy(update={"bounds": bounds})
