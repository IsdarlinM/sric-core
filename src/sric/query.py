from __future__ import annotations

import shlex
from datetime import datetime
from typing import Any

from .graph import TemporalGraph


class GraphQueryError(ValueError):
    pass


class SecurityResearchGraphQuery:
    """Small deterministic read-only graph query language.

    Grammar (case-insensitive keywords):
      MATCH <node_type|*> [LABEL <text>] [EDGE <edge_type|*> TO <node_type|*>] [AT <iso8601>]

    This is intentionally read-only and does not execute arbitrary expressions or code.
    """

    def __init__(self, graph: TemporalGraph) -> None:
        self.graph = graph

    def execute(self, expression: str) -> dict[str, Any]:
        try:
            tokens = shlex.split(expression)
        except ValueError as exc:
            raise GraphQueryError(f"invalid query quoting: {exc}") from exc
        if len(tokens) < 2 or tokens[0].upper() != "MATCH":
            raise GraphQueryError("query must start with MATCH <node_type|*>")
        node_type = tokens[1]
        label: str | None = None
        edge_type: str | None = None
        target_type: str | None = None
        at: datetime | None = None
        idx = 2
        while idx < len(tokens):
            keyword = tokens[idx].upper()
            if keyword == "LABEL":
                if idx + 1 >= len(tokens):
                    raise GraphQueryError("LABEL requires text")
                label = tokens[idx + 1]
                idx += 2
            elif keyword == "EDGE":
                if idx + 3 >= len(tokens) or tokens[idx + 2].upper() != "TO":
                    raise GraphQueryError("EDGE requires: EDGE <edge_type|*> TO <node_type|*>")
                edge_type = tokens[idx + 1]
                target_type = tokens[idx + 3]
                idx += 4
            elif keyword == "AT":
                if idx + 1 >= len(tokens):
                    raise GraphQueryError("AT requires ISO-8601 timestamp")
                try:
                    at = datetime.fromisoformat(tokens[idx + 1].replace("Z", "+00:00"))
                except ValueError as exc:
                    raise GraphQueryError("AT requires a valid ISO-8601 timestamp") from exc
                idx += 2
            else:
                raise GraphQueryError(f"unsupported query keyword: {tokens[idx]}")

        snapshot = self.graph.snapshot(at)
        nodes = snapshot["nodes"]
        edges = snapshot["edges"]
        matched_nodes = [
            node
            for node in nodes
            if (node_type == "*" or str(node.get("node_type", "")).casefold() == node_type.casefold())
            and (label is None or label.casefold() in str(node.get("label", "")).casefold())
        ]
        if edge_type is None:
            return {"query": expression, "mode": "READ_ONLY", "nodes": matched_nodes, "edges": []}

        ids = {str(node["node_id"]) for node in matched_nodes}
        by_id = {str(node["node_id"]): node for node in nodes}
        matched_edges: list[dict[str, Any]] = []
        target_nodes: dict[str, dict[str, Any]] = {}
        for edge in edges:
            if str(edge.get("source_node_id")) not in ids:
                continue
            if edge_type != "*" and str(edge.get("edge_type", "")).casefold() != edge_type.casefold():
                continue
            target = by_id.get(str(edge.get("target_node_id")))
            if target is None:
                continue
            if target_type != "*" and str(target.get("node_type", "")).casefold() != str(target_type).casefold():
                continue
            matched_edges.append(edge)
            target_nodes[str(target["node_id"])] = target
        return {
            "query": expression,
            "mode": "READ_ONLY",
            "nodes": matched_nodes,
            "edges": matched_edges,
            "targets": list(target_nodes.values()),
        }
