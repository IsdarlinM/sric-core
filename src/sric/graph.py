from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str = Field(default_factory=lambda: f"N-{uuid4().hex[:12].upper()}")
    node_type: str
    label: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edge_id: str = Field(default_factory=lambda: f"E-{uuid4().hex[:12].upper()}")
    source_node_id: str
    target_node_id: str
    edge_type: str
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    discovery_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalGraph:
    """Small local-first persistent graph abstraction used by all SRIC products.

    This deliberately starts as deterministic JSON storage rather than forcing a graph database.
    The public model can later be backed by SQLite/PostgreSQL/Memgraph without changing callers.
    """

    def __init__(self, workspace: Path) -> None:
        self.path = workspace / "graph.json"
        if not self.path.exists():
            self._save({"schema_version": "1", "nodes": [], "edges": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("graph store must contain a JSON object")
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def upsert_node(self, node: GraphNode) -> GraphNode:
        data = self._load()
        nodes = data.setdefault("nodes", [])
        for idx, existing in enumerate(nodes):
            if existing.get("node_id") == node.node_id:
                nodes[idx] = node.model_dump(mode="json")
                self._save(data)
                return node
        nodes.append(node.model_dump(mode="json"))
        self._save(data)
        return node

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        data = self._load()
        node_ids = {str(n["node_id"]) for n in data.get("nodes", [])}
        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            raise ValueError("edge references unknown graph node")
        edges = data.setdefault("edges", [])
        for idx, existing in enumerate(edges):
            if existing.get("edge_id") == edge.edge_id:
                edges[idx] = edge.model_dump(mode="json")
                self._save(data)
                return edge
        edges.append(edge.model_dump(mode="json"))
        self._save(data)
        return edge

    def snapshot(self, at: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
        data = self._load()
        nodes = [GraphNode.model_validate(x) for x in data.get("nodes", [])]
        edges = [GraphEdge.model_validate(x) for x in data.get("edges", [])]
        if at is None:
            return {
                "nodes": [n.model_dump(mode="json") for n in nodes],
                "edges": [e.model_dump(mode="json") for e in edges],
            }
        when = at if at.tzinfo else at.replace(tzinfo=timezone.utc)

        def node_visible(node: GraphNode) -> bool:
            start = node.first_seen or node.observed_at
            end = node.last_seen
            start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            if start > when:
                return False
            if end is None:
                return True
            end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
            return end >= when

        visible_nodes = {n.node_id for n in nodes if node_visible(n)}
        visible_edges: list[GraphEdge] = []
        for edge in edges:
            if edge.source_node_id not in visible_nodes or edge.target_node_id not in visible_nodes:
                continue
            start = edge.valid_from or edge.observed_at
            start = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            if start > when:
                continue
            if edge.valid_to is not None:
                end = edge.valid_to if edge.valid_to.tzinfo else edge.valid_to.replace(tzinfo=timezone.utc)
                if end < when:
                    continue
            visible_edges.append(edge)
        return {
            "nodes": [n.model_dump(mode="json") for n in nodes if n.node_id in visible_nodes],
            "edges": [e.model_dump(mode="json") for e in visible_edges],
        }

    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        needle = query.casefold().strip()
        if not needle:
            return []
        data = self._load()
        matches: list[dict[str, Any]] = []
        for kind in ("nodes", "edges"):
            for item in data.get(kind, []):
                haystack = json.dumps(item, default=str).casefold()
                if needle in haystack:
                    matches.append({"kind": kind[:-1], "item": item})
                    if len(matches) >= limit:
                        return matches
        return matches

    def neighbors(self, node_id: str) -> dict[str, list[dict[str, Any]]]:
        data = self._load()
        incoming = [e for e in data.get("edges", []) if e.get("target_node_id") == node_id]
        outgoing = [e for e in data.get("edges", []) if e.get("source_node_id") == node_id]
        return {"incoming": incoming, "outgoing": outgoing}
