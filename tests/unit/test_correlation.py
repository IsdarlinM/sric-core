from sric.correlation import CorrelationEngine, CorrelationFact, historical_active_relevance_rule


def test_correlation_is_hypothesis_and_explainable():
    e = CorrelationEngine()
    e.register(historical_active_relevance_rule())
    results = e.evaluate([
        CorrelationFact(fact_id="F1", fact_type="historical_endpoint", value="/v1/export", source="archive", evidence_ids=["E1"]),
        CorrelationFact(fact_id="F2", fact_type="current_dns", value="api.example", source="dns", evidence_ids=["E2"]),
    ])
    assert len(results) == 1
    assert results[0].status == "HYPOTHESIS"
    assert set(results[0].evidence_ids) == {"E1","E2"}
