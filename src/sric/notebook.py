from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class NotebookEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_id: str = Field(default_factory=lambda: f"NB-{uuid4().hex[:12].upper()}")
    entry_type: str
    title: str
    body: str
    status: str = "OBSERVED"
    evidence_ids: list[str] = Field(default_factory=list)
    parent_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchNotebook:
    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "research-notebook.json"
        if not self.path.exists():
            self._save({"schema_version": "1", "entries": [], "saved_queries": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("notebook store must contain a JSON object")
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def add(self, entry: NotebookEntry) -> NotebookEntry:
        data = self._load()
        known = {str(x["entry_id"]) for x in data["entries"]}
        unknown = [p for p in entry.parent_ids if p not in known]
        if unknown:
            raise ValueError(f"unknown notebook parents: {', '.join(unknown)}")
        data["entries"].append(entry.model_dump(mode="json"))
        self._save(data)
        return entry

    def list(self) -> list[NotebookEntry]:
        return [NotebookEntry.model_validate(x) for x in self._load()["entries"]]

    def save_query(self, name: str, query: str) -> None:
        if not name.strip() or not query.strip():
            raise ValueError("saved query requires name and query")
        data = self._load()
        queries = [x for x in data["saved_queries"] if x.get("name") != name]
        queries.append({"name": name, "query": query})
        data["saved_queries"] = queries
        self._save(data)

    def saved_queries(self) -> list[dict[str, str]]:
        raw = self._load()["saved_queries"]
        return [{"name": str(x["name"]), "query": str(x["query"])} for x in raw]
