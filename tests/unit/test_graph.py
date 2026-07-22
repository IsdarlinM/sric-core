from datetime import datetime, timezone
from sric.graph import GraphEdge, GraphNode, TemporalGraph


def test_temporal_graph_snapshot_search_and_neighbors(tmp_path):
    g = TemporalGraph(tmp_path)
    a = g.upsert_node(GraphNode(node_id="A", node_type="domain", label="old.example", source="test", first_seen=datetime(2020,1,1,tzinfo=timezone.utc)))
    b = g.upsert_node(GraphNode(node_id="B", node_type="api", label="legacy api", source="test", first_seen=datetime(2021,1,1,tzinfo=timezone.utc)))
    g.upsert_edge(GraphEdge(edge_id="E1", source_node_id=a.node_id, target_node_id=b.node_id, edge_type="references", discovery_method="fixture", valid_from=datetime(2021,1,1,tzinfo=timezone.utc)))
    assert len(g.snapshot()["nodes"]) == 2
    assert g.snapshot(datetime(2020,6,1,tzinfo=timezone.utc))["edges"] == []
    assert g.search("legacy")[0]["item"]["node_id"] == "B"
    assert len(g.neighbors("B")["incoming"]) == 1
