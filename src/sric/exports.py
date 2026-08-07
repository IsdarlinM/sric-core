from __future__ import annotations

import json
from typing import Any, Sequence
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import BaseModel, ConfigDict, Field
from sric.models import ClaimStatus


class ExportNode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    node_type: str
    label: str | None = None
    status: ClaimStatus = ClaimStatus.UNKNOWN
    evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


class ExportEdge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: str
    source_id: str
    target_id: str
    edge_type: str
    status: ClaimStatus = ClaimStatus.UNKNOWN
    evidence_ids: list[str] = Field(default_factory=list)
    counter_evidence_ids: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)


def export_jsonld(
    nodes: Sequence[ExportNode],
    edges: Sequence[ExportEdge],
) -> str:
    known = {node.node_id for node in nodes}
    for edge in edges:
        if edge.source_id not in known or edge.target_id not in known:
            raise ValueError("all exported edges must reference exported nodes")
    graph: list[dict[str, Any]] = []
    for node in sorted(nodes, key=lambda item: item.node_id):
        graph.append(
            {
                "@id": node.node_id,
                "@type": node.node_type,
                "label": node.label,
                "status": node.status.value,
                "evidence": sorted(node.evidence_ids),
                **node.attributes,
            }
        )
    for edge in sorted(edges, key=lambda item: item.edge_id):
        graph.append(
            {
                "@id": edge.edge_id,
                "@type": edge.edge_type,
                "source": {"@id": edge.source_id},
                "target": {"@id": edge.target_id},
                "status": edge.status.value,
                "evidence": sorted(edge.evidence_ids),
                "counterEvidence": sorted(edge.counter_evidence_ids),
                **edge.attributes,
            }
        )
    return json.dumps(
        {
            "@context": {
                "status": "https://sentinel-forge.dev/schema/status",
                "evidence": "https://sentinel-forge.dev/schema/evidence",
                "counterEvidence": "https://sentinel-forge.dev/schema/counter-evidence",
                "source": {"@type": "@id"},
                "target": {"@type": "@id"},
            },
            "@graph": graph,
        },
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ) + "\n"


def export_graphml(
    nodes: Sequence[ExportNode],
    edges: Sequence[ExportEdge],
) -> str:
    known = {node.node_id for node in nodes}
    for edge in edges:
        if edge.source_id not in known or edge.target_id not in known:
            raise ValueError("all exported edges must reference exported nodes")

    root = Element("graphml", xmlns="http://graphml.graphdrawing.org/xmlns")
    for key_id, target, name in (
        ("node_type", "node", "node_type"),
        ("node_status", "node", "status"),
        ("node_evidence", "node", "evidence_ids"),
        ("edge_type", "edge", "edge_type"),
        ("edge_status", "edge", "status"),
        ("edge_evidence", "edge", "evidence_ids"),
        ("edge_counter", "edge", "counter_evidence_ids"),
    ):
        SubElement(
            root,
            "key",
            id=key_id,
            **{"for": target, "attr.name": name, "attr.type": "string"},
        )
    graph = SubElement(root, "graph", id="G", edgedefault="directed")
    for node in sorted(nodes, key=lambda item: item.node_id):
        element = SubElement(graph, "node", id=node.node_id)
        SubElement(element, "data", key="node_type").text = node.node_type
        SubElement(element, "data", key="node_status").text = node.status.value
        SubElement(element, "data", key="node_evidence").text = json.dumps(
            sorted(node.evidence_ids), separators=(",", ":")
        )
    for edge in sorted(edges, key=lambda item: item.edge_id):
        element = SubElement(
            graph,
            "edge",
            id=edge.edge_id,
            source=edge.source_id,
            target=edge.target_id,
        )
        SubElement(element, "data", key="edge_type").text = edge.edge_type
        SubElement(element, "data", key="edge_status").text = edge.status.value
        SubElement(element, "data", key="edge_evidence").text = json.dumps(
            sorted(edge.evidence_ids), separators=(",", ":")
        )
        SubElement(element, "data", key="edge_counter").text = json.dumps(
            sorted(edge.counter_evidence_ids), separators=(",", ":")
        )
    return tostring(root, encoding="unicode", xml_declaration=True) + "\n"
