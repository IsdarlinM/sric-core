import json
from xml.etree import ElementTree

import pytest

from sric.exports import ExportEdge, ExportNode, export_graphml, export_jsonld
from sric.models import ClaimStatus


def graph() -> tuple[list[ExportNode], list[ExportEdge]]:
    nodes = [
        ExportNode(
            node_id="asset-1",
            node_type="Asset",
            status=ClaimStatus.OBSERVED,
            evidence_ids=["E-1"],
        ),
        ExportNode(
            node_id="org-1",
            node_type="Organization",
            status=ClaimStatus.INFERRED,
            evidence_ids=["E-2"],
        ),
    ]
    edges = [
        ExportEdge(
            edge_id="R-1",
            source_id="org-1",
            target_id="asset-1",
            edge_type="POSSIBLY_RELATED",
            status=ClaimStatus.INFERRED,
            evidence_ids=["E-3"],
            counter_evidence_ids=["CE-1"],
        )
    ]
    return nodes, edges


def test_jsonld_export_is_deterministic_and_evidence_bearing() -> None:
    nodes, edges = graph()

    first = export_jsonld(nodes, edges)
    second = export_jsonld(list(reversed(nodes)), list(reversed(edges)))
    payload = json.loads(first)

    assert first == second
    relationship = next(item for item in payload["@graph"] if item["@id"] == "R-1")
    assert relationship["status"] == "INFERRED"
    assert relationship["counterEvidence"] == ["CE-1"]


def test_graphml_export_is_valid_xml_with_status_and_evidence() -> None:
    nodes, edges = graph()
    xml = export_graphml(nodes, edges)
    root = ElementTree.fromstring(xml)

    assert root.tag.endswith("graphml")
    assert "POSSIBLY_RELATED" in xml
    assert "CE-1" in xml


def test_exports_reject_edges_to_missing_nodes() -> None:
    nodes, edges = graph()
    edges[0].target_id = "missing"

    with pytest.raises(ValueError, match="reference exported nodes"):
        export_jsonld(nodes, edges)
    with pytest.raises(ValueError, match="reference exported nodes"):
        export_graphml(nodes, edges)
