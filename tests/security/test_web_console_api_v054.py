from __future__ import annotations

import re
import time

from fastapi.testclient import TestClient

from sric import __version__
from sric.api import create_app


TOKEN_RE = re.compile(r'name="sentinel-console-token" content="([^"]+)"')


def _token(client: TestClient) -> str:
    response = client.get("/console")
    assert response.status_code == 200
    match = TOKEN_RE.search(response.text)
    assert match is not None
    return match.group(1)


def test_console_page_uses_same_origin_csp_and_catalog_is_not_a_shell() -> None:
    client = TestClient(create_app())
    page = client.get("/console")
    assert page.status_code == 200
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp
    assert "connect-src 'self'" in csp
    catalog = client.get("/api/v1/console/catalog")
    assert catalog.status_code == 200
    execution = catalog.json()["execution"]
    assert execution["shell"] is False
    assert execution["arbitrary_executable"] is False
    assert execution["mutations_require_approval"] is True


def test_console_mutations_require_csrf_token_and_human_approval() -> None:
    client = TestClient(create_app())
    missing_token = client.post(
        "/api/v1/console/jobs",
        json={"command": "update", "args": [], "approved": True},
    )
    assert missing_token.status_code == 403

    token = _token(client)
    missing_approval = client.post(
        "/api/v1/console/jobs",
        headers={"X-Sentinel-Console-Token": token},
        json={"command": "update", "args": []},
    )
    assert missing_approval.status_code == 409
    assert "approval" in missing_approval.json()["detail"].lower()


def test_console_refuses_recursive_web_server_command() -> None:
    client = TestClient(create_app())
    token = _token(client)
    response = client.post(
        "/api/v1/console/jobs",
        headers={"X-Sentinel-Console-Token": token},
        json={"command": "web", "args": []},
    )
    assert response.status_code == 409
    assert "already running" in response.json()["detail"]


def test_console_executes_real_safe_cli_command_through_fixed_runner() -> None:
    client = TestClient(create_app())
    token = _token(client)
    created = client.post(
        "/api/v1/console/jobs",
        headers={"X-Sentinel-Console-Token": token},
        json={"command": "version", "args": []},
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]

    payload = created.json()
    for _ in range(100):
        payload = client.get(f"/api/v1/console/jobs/{job_id}").json()
        if payload["status"] in {"succeeded", "failed", "cancelled", "timed_out"}:
            break
        time.sleep(0.05)

    assert payload["status"] == "succeeded"
    assert payload["returncode"] == 0
    assert __version__ in payload["output"]
