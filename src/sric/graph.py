from __future__ import annotations

import json
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .models import ClaimStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class GraphNode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    node_id: str = Field(default_factory=lambda: f"N-{uuid4().hex[:12].upper()}")
    node_type: str
    label: str
    status: ClaimStatus = ClaimStatus.OBSERVED
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    source: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_independence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    provenance_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")
    edge_id: str = Field(default_factory=lambda: f"E-{uuid4().hex[:12].upper()}")
    source_node_id: str
    target_node_id: str
    edge_type: str
    status: ClaimStatus = ClaimStatus.INFERRED
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    observed_at: datetime = Field(default_factory=utcnow)
    source: str = "unknown"
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_independence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    discovery_method: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalGraph:
    """Deterministic local-first temporal security graph shared by all products.

    The on-disk representation remains JSON for portability, while the public API is designed so a
    database-backed repository can replace storage without changing product models.
    """

    def __init__(self, workspace: Path) -> None:
        graph_dir = workspace / "graph"
        self.storage_path = (graph_dir / "graph.json") if graph_dir.is_dir() else (workspace / "graph.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.storage_path.exists():
            self._save({"schema_version": "2", "nodes": [], "edges": []})

    def _load(self) -> dict[str, Any]:
        raw = json.loads(self.storage_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("graph store must contain a JSON object")
        raw.setdefault("schema_version", "1")
        raw.setdefault("nodes", [])
        raw.setdefault("edges", [])
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        data["schema_version"] = "2"
        tmp = self.storage_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.storage_path)

    def upsert_node(self, node: GraphNode) -> GraphNode:
        data = self._load(); nodes = data.setdefault("nodes", [])
        for idx, existing in enumerate(nodes):
            if existing.get("node_id") == node.node_id:
                nodes[idx] = node.model_dump(mode="json"); self._save(data); return node
        nodes.append(node.model_dump(mode="json")); self._save(data); return node

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        data = self._load(); node_ids = {str(n["node_id"]) for n in data.get("nodes", [])}
        if edge.source_node_id not in node_ids or edge.target_node_id not in node_ids:
            raise ValueError("edge references unknown graph node")
        edges = data.setdefault("edges", [])
        for idx, existing in enumerate(edges):
            if existing.get("edge_id") == edge.edge_id:
                edges[idx] = edge.model_dump(mode="json"); self._save(data); return edge
        edges.append(edge.model_dump(mode="json")); self._save(data); return edge

    def get_node(self, node_id: str) -> GraphNode:
        for raw in self._load()["nodes"]:
            if raw.get("node_id") == node_id: return GraphNode.model_validate(raw)
        raise KeyError(node_id)

    def get_edge(self, edge_id: str) -> GraphEdge:
        for raw in self._load()["edges"]:
            if raw.get("edge_id") == edge_id: return GraphEdge.model_validate(raw)
        raise KeyError(edge_id)

    def snapshot(self, at: datetime | None = None) -> dict[str, list[dict[str, Any]]]:
        data = self._load(); nodes = [GraphNode.model_validate(x) for x in data.get("nodes", [])]; edges = [GraphEdge.model_validate(x) for x in data.get("edges", [])]
        if at is None:
            return {"nodes":[n.model_dump(mode="json") for n in nodes],"edges":[e.model_dump(mode="json") for e in edges]}
        when=_aware(at)
        def node_visible(node: GraphNode)->bool:
            start=_aware(node.first_seen or node.observed_at); end=node.last_seen
            return start<=when and (end is None or _aware(end)>=when)
        visible={n.node_id for n in nodes if node_visible(n)}; visible_edges=[]
        for edge in edges:
            if edge.source_node_id not in visible or edge.target_node_id not in visible: continue
            start=_aware(edge.valid_from or edge.first_seen or edge.observed_at)
            if start>when: continue
            end=edge.valid_to or edge.last_seen
            if end is not None and _aware(end)<when: continue
            visible_edges.append(edge)
        return {"nodes":[n.model_dump(mode="json") for n in nodes if n.node_id in visible],"edges":[e.model_dump(mode="json") for e in visible_edges]}

    def search(self, query: str, limit: int = 50, *, offset: int = 0) -> list[dict[str, Any]]:
        if limit<1 or limit>500: raise ValueError("limit must be between 1 and 500")
        if offset<0: raise ValueError("offset must be >= 0")
        needle=query.casefold().strip()
        if not needle: return []
        matches=[]
        for kind in ("nodes","edges"):
            for item in self._load().get(kind,[]):
                if needle in json.dumps(item,default=str).casefold(): matches.append({"kind":kind[:-1],"item":item})
        return matches[offset:offset+limit]

    def neighbors(self, node_id: str) -> dict[str, list[dict[str, Any]]]:
        self.get_node(node_id); data=self._load(); incoming=[e for e in data["edges"] if e.get("target_node_id")==node_id]; outgoing=[e for e in data["edges"] if e.get("source_node_id")==node_id]
        return {"incoming":incoming,"outgoing":outgoing}

    def explain(self, object_id: str) -> dict[str, Any]:
        try:
            obj=self.get_node(object_id).model_dump(mode="json"); kind="node"
        except KeyError:
            obj=self.get_edge(object_id).model_dump(mode="json"); kind="edge"
        return {"kind":kind,"object":obj,"why": {"status":obj.get("status"),"confidence":obj.get("confidence"),"source":obj.get("source"),"evidence_ids":obj.get("evidence_ids",[]),"counter_evidence_ids":obj.get("counter_evidence_ids",[]),"source_independence":obj.get("source_independence",0.0)}}

    def path(self, source_node_id: str, target_node_id: str, *, max_depth: int = 8) -> dict[str, Any]:
        if max_depth<1 or max_depth>32: raise ValueError("max_depth must be between 1 and 32")
        self.get_node(source_node_id); self.get_node(target_node_id); edges=[GraphEdge.model_validate(x) for x in self._load()["edges"]]
        adjacency: dict[str,list[GraphEdge]]={}
        for edge in edges: adjacency.setdefault(edge.source_node_id,[]).append(edge)
        q: deque[tuple[str, list[str], list[str]]] = deque(
            [(source_node_id, [], [source_node_id])]
        ); seen={source_node_id}
        while q:
            current,path_edges,path_nodes=q.popleft()
            if len(path_edges)>=max_depth: continue
            for edge in sorted(adjacency.get(current,[]),key=lambda x:x.edge_id):
                nxt=edge.target_node_id
                new_edges=[*path_edges,edge.edge_id]; new_nodes=[*path_nodes,nxt]
                if nxt==target_node_id: return {"found":True,"nodes":new_nodes,"edges":new_edges}
                if nxt not in seen: seen.add(nxt); q.append((nxt,new_edges,new_nodes))
        return {"found":False,"nodes":[],"edges":[]}

    def history(self, object_id: str) -> list[dict[str, Any]]:
        explanation=self.explain(object_id); obj=explanation["object"]
        points=[]
        for key in ("first_seen","valid_from","observed_at","last_seen","valid_to"):
            if obj.get(key): points.append({"timestamp":obj[key],"event":key,"object_id":object_id})
        return sorted(points,key=lambda x:str(x["timestamp"]))

    def diff(self, before: datetime, after: datetime) -> dict[str, Any]:
        if _aware(before)>_aware(after): raise ValueError("before must be <= after")
        a=self.snapshot(before); b=self.snapshot(after)
        an={x["node_id"]:x for x in a["nodes"]}; bn={x["node_id"]:x for x in b["nodes"]}; ae={x["edge_id"]:x for x in a["edges"]}; be={x["edge_id"]:x for x in b["edges"]}
        return {"nodes_added":[bn[k] for k in sorted(bn.keys()-an.keys())],"nodes_removed":[an[k] for k in sorted(an.keys()-bn.keys())],"nodes_changed":[{"before":an[k],"after":bn[k]} for k in sorted(an.keys()&bn.keys()) if an[k]!=bn[k]],"edges_added":[be[k] for k in sorted(be.keys()-ae.keys())],"edges_removed":[ae[k] for k in sorted(ae.keys()-be.keys())],"edges_changed":[{"before":ae[k],"after":be[k]} for k in sorted(ae.keys()&be.keys()) if ae[k]!=be[k]]}
