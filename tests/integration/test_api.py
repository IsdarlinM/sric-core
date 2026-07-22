from fastapi.testclient import TestClient
from sric.api import create_app


def test_health_and_security_headers() -> None:
    r = TestClient(create_app()).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "default-src 'none'" in r.headers["content-security-policy"]
