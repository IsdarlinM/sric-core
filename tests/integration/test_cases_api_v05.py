from fastapi.testclient import TestClient

from sric.api_vnext import create_app


def test_case_analysis_and_fingerprint_api() -> None:
    client = TestClient(create_app())
    fingerprint = client.post(
        "/api/v1/evidence-native/claims/fingerprint",
        json={
            "claim_type": "authorization",
            "subject": "actor-a",
            "predicate": "read",
            "object_value": "resource-1",
            "context": {"tenant": "t1"},
        },
    )
    assert fingerprint.status_code == 200
    assert fingerprint.json()["claim_fingerprint"].startswith("claim:")
    assert fingerprint.json()["validated_finding_created"] is False

    response = client.post(
        "/api/v1/evidence-native/cases/analyze",
        json={
            "case": {
                "case_id": "case-1",
                "title": "Example",
                "artifacts": [
                    {
                        "artifact_id": "a1",
                        "artifact_type": "HYPOTHESIS",
                        "source_tool": "authtwin",
                        "source_ref": "cell:1",
                        "status": "UNKNOWN",
                        "evidence_ids": ["ev-1"],
                    }
                ],
            },
            "required_evidence": ["ev-1", "ev-2"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["evidence_adequacy"] == 0.5
    assert payload["unresolved_artifact_ids"] == ["a1"]
    assert payload["truth_state_modified"] is False
