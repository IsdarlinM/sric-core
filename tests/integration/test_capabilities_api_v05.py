from fastapi.testclient import TestClient

from sric.api_vnext import create_app


def test_capabilities_api_is_read_only_and_available() -> None:
    response = TestClient(create_app()).get("/api/v1/evidence-native/capabilities")
    assert response.status_code == 200
    payload = response.json()
    assert payload["core_distribution"] == "sric-core"
    assert isinstance(payload["products"], list)
    assert "available_capabilities" in payload
