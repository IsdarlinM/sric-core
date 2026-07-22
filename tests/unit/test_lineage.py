import pytest
from sric.lineage import EvidenceLineage, LineageRecord


def test_lineage_requires_known_parents_and_explains(tmp_path):
    l = EvidenceLineage(tmp_path)
    l.append(LineageRecord(artifact_id="OBS-1", artifact_type="observation", status="OBSERVED", source="fixture", method="import"))
    l.append(LineageRecord(artifact_id="CLM-1", artifact_type="claim", status="HYPOTHESIS", source="analyst", method="rule", parent_ids=["OBS-1"], evidence_ids=["EVD-1"]))
    explained = l.explain("CLM-1")
    assert [x["artifact_id"] for x in explained["chain"]] == ["OBS-1", "CLM-1"]
    with pytest.raises(ValueError):
        l.append(LineageRecord(artifact_id="X", artifact_type="claim", status="UNKNOWN", source="x", method="x", parent_ids=["MISSING"]))
