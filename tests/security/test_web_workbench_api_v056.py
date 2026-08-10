from __future__ import annotations

import re

from fastapi.testclient import TestClient

from sric.api import create_app
from sric.web_console import build_command_catalog


def _token(html: str) -> str:
    match = re.search(r'name="sentinel-workbench-token" content="([^"]+)"', html)
    assert match is not None
    return match.group(1)


def test_root_redirects_to_full_workbench() -> None:
    client = TestClient(create_app())
    response = client.get("/", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/workbench"


def test_workbench_assets_and_csp_are_same_origin_only() -> None:
    client = TestClient(create_app())
    page = client.get("/workbench")
    assert page.status_code == 200
    assert "guided security operations" in page.text
    assert "No command syntax is required" in page.text
    assert "Advanced argv" not in page.text
    assert "Additional arguments" not in page.text
    assert "id=\"extra-args\"" not in page.text
    assert "href=\"/console\"" not in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert "connect-src 'self'" in page.headers["content-security-policy"]
    assert client.get("/workbench/styles.css").status_code == 200
    script = client.get("/workbench/app.js")
    assert script.status_code == 200
    assert "tokenize(extra" not in script.text
    assert "user supplied argv" not in script.text.lower()


def test_workbench_catalog_matches_every_cli_command_and_argument() -> None:
    client = TestClient(create_app())
    payload = client.get("/api/v1/workbench/catalog").json()
    cli = {item["path"]: item for item in build_command_catalog("sric.cli_all")}
    web = {item["path"]: item for item in payload["features"]}

    assert payload["schema_version"] == 2
    assert payload["contract"]["complete"] is True
    assert payload["execution"] == {
        "backend": "web-console-fixed-runner",
        "shell": False,
        "arbitrary_executable": False,
        "user_supplied_argv": False,
        "mutations_require_approval": True,
    }
    assert set(web) == set(cli)
    for path, command in cli.items():
        assert [item["name"] for item in web[path]["params"]] == [
            item["name"] for item in command["params"]
        ]


def test_workbench_uses_existing_csrf_and_mutation_approval_gate() -> None:
    client = TestClient(create_app())
    page = client.get("/workbench")
    token = _token(page.text)

    no_token = client.post("/api/v1/console/jobs", json={"command": "update", "args": []})
    assert no_token.status_code == 403

    no_approval = client.post(
        "/api/v1/console/jobs",
        headers={"X-Sentinel-Console-Token": token},
        json={"command": "update", "args": [], "approved": False},
    )
    assert no_approval.status_code == 409
