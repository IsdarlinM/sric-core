from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LineageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str = Field(default_factory=lambda: f"LIN-{uuid4().hex[:12].upper()}")
    artifact_id: str
    artifact_type: str
    status: str
    evidence_ids: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    source: str
    method: str
    timestamp: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvidenceLineage:
    """Trace raw evidence through observations, claims, validations and findings."""

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "lineage.json"
        if not self.path.exists():
            self._save({"schema_version": "1", "records": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("lineage store must contain a JSON object")
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def append(self, record: LineageRecord) -> LineageRecord:
        data = self._load()
        known = {str(x["artifact_id"]) for x in data["records"]}
        unknown = [p for p in record.parent_ids if p not in known]
        if unknown:
            raise ValueError(f"unknown lineage parents: {', '.join(unknown)}")
        data["records"].append(record.model_dump(mode="json"))
        self._save(data)
        return record

    def explain(self, artifact_id: str) -> dict[str, Any]:
        records = [LineageRecord.model_validate(x) for x in self._load()["records"]]
        by_id = {r.artifact_id: r for r in records}
        if artifact_id not in by_id:
            raise KeyError(artifact_id)
        visited: set[str] = set()
        chain: list[LineageRecord] = []

        def walk(item_id: str) -> None:
            if item_id in visited:
                return
            visited.add(item_id)
            item = by_id[item_id]
            for parent in item.parent_ids:
                walk(parent)
            chain.append(item)

        walk(artifact_id)
        target = by_id[artifact_id]
        return {
            "artifact": target.model_dump(mode="json"),
            "chain": [x.model_dump(mode="json") for x in chain],
            "why_am_i_seeing_this": {
                "status": target.status,
                "evidence_ids": target.evidence_ids,
                "source": target.source,
                "method": target.method,
                "parents": target.parent_ids,
            },
        }
