import hashlib

from fastapi.testclient import TestClient

from sric.api_vnext import create_app


def test_confidence_api_abstains_when_required_evidence_is_missing() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/evidence-native/confidence/analyze",
        json={
            "signals": [
                {
                    "signal": "runtime-observation",
                    "contribution": 0.8,
                    "reason": "Observed response",
                    "source_id": "source-1",
                    "evidence_ids": ["E-1"],
                    "direct_observation": True,
                    "source_quality": 1.0,
                    "specificity": 1.0,
                }
            ],
            "missing_required_evidence": ["negative control"],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["skeptic_review"]["verdict"] == "UNKNOWN"
    assert payload["validated_finding_created"] is False


def test_confidence_api_rejects_zero_maximum_at_validation_boundary() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/evidence-native/confidence/analyze",
        json={"signals": [], "maximum": 0},
    )
    assert response.status_code == 422


def test_calibration_api_rejects_non_binary_outcomes_and_invalid_probabilities() -> None:
    client = TestClient(create_app())
    assert client.post(
        "/api/v1/evidence-native/confidence/calibration",
        json={"probabilities": [0.8], "outcomes": [2]},
    ).status_code == 422
    assert client.post(
        "/api/v1/evidence-native/confidence/calibration",
        json={"probabilities": [1.5], "outcomes": [1]},
    ).status_code == 422


def test_bitemporal_api_does_not_use_future_knowledge() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/evidence-native/bitemporal/query",
        json={
            "valid_at": "2026-01-15T00:00:00Z",
            "known_at": "2026-01-15T00:00:00Z",
            "records": [
                {
                    "record_id": "R-OLD",
                    "entity_id": "asset-1",
                    "fact_type": "owner",
                    "value": "org-a",
                    "status": "OBSERVED",
                    "source_id": "source-1",
                    "evidence_ids": ["E-OLD"],
                    "bounds": {
                        "valid_from": "2026-01-01T00:00:00Z",
                        "recorded_at": "2026-01-10T00:00:00Z",
                    },
                },
                {
                    "record_id": "R-FUTURE",
                    "entity_id": "asset-1",
                    "fact_type": "owner",
                    "value": "org-b",
                    "status": "OBSERVED",
                    "source_id": "source-2",
                    "evidence_ids": ["E-FUTURE"],
                    "bounds": {
                        "valid_from": "2026-01-01T00:00:00Z",
                        "recorded_at": "2026-02-01T00:00:00Z",
                    },
                },
            ],
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert [item["record_id"] for item in payload["records"]] == ["R-OLD"]
    assert payload["future_knowledge_used"] is False


def test_source_api_collapses_mirrors_by_upstream() -> None:
    client = TestClient(create_app())
    response = client.post(
        "/api/v1/evidence-native/sources/independence",
        json={
            "sources": [
                {"source_id": "primary", "source_type": "registry", "independently_operated": True},
                {"source_id": "mirror-a", "source_type": "mirror", "upstream_source_ids": ["primary"]},
                {"source_id": "mirror-b", "source_type": "mirror", "upstream_source_ids": ["primary"]},
            ]
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["source_groups"]["mirror-a"] == payload["source_groups"]["mirror-b"]
    assert payload["independent_group_count"] == 2


def test_merkle_api_returns_proof_without_claiming_truthfulness() -> None:
    client = TestClient(create_app())
    evidence = [
        {"evidence_id": "E-1", "content_sha256": hashlib.sha256(b"one").hexdigest()},
        {"evidence_id": "E-2", "content_sha256": hashlib.sha256(b"two").hexdigest()},
    ]
    response = client.post(
        "/api/v1/evidence-native/integrity/merkle",
        json={"evidence": evidence, "prove_evidence_id": "E-2"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["root_sha256"]) == 64
    assert payload["proof"]["leaf_index"] == 1
    assert payload["truthfulness_proved"] is False


def test_merkle_api_handles_empty_and_missing_proof_target_without_traceback() -> None:
    client = TestClient(create_app())
    empty = client.post("/api/v1/evidence-native/integrity/merkle", json={"evidence": []})
    assert empty.status_code == 400
    evidence = [{"evidence_id": "E-1", "content_sha256": hashlib.sha256(b"one").hexdigest()}]
    missing = client.post(
        "/api/v1/evidence-native/integrity/merkle",
        json={"evidence": evidence, "prove_evidence_id": "missing"},
    )
    assert missing.status_code == 404
