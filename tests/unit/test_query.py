from sric.graph import GraphEdge, GraphNode, TemporalGraph
from sric.query import GraphQueryError, SecurityResearchGraphQuery


def test_read_only_graph_query_language(tmp_path):
    graph = TemporalGraph(tmp_path)
    graph.upsert_node(GraphNode(node_id="a", node_type="actor", label="Actor B", source="test"))
    graph.upsert_node(GraphNode(node_id="r", node_type="resource", label="Report", source="test"))
    graph.upsert_edge(GraphEdge(edge_id="e", source_node_id="a", target_node_id="r", edge_type="can_read", discovery_method="test"))
    result = SecurityResearchGraphQuery(graph).execute('MATCH actor LABEL "Actor B" EDGE can_read TO resource')
    assert result["mode"] == "READ_ONLY"
    assert [x["node_id"] for x in result["nodes"]] == ["a"]
    assert [x["edge_id"] for x in result["edges"]] == ["e"]
    assert [x["node_id"] for x in result["targets"]] == ["r"]


def test_graph_query_rejects_arbitrary_language(tmp_path):
    graph = TemporalGraph(tmp_path)
    try:
        SecurityResearchGraphQuery(graph).execute("DELETE EVERYTHING")
    except GraphQueryError:
        pass
    else:
        raise AssertionError("mutating/arbitrary language must be rejected")
