from fastapi.testclient import TestClient

from sric.api import create_app
from sric.web_security_workspace import SECURITY_WORKSPACE_CSS, SECURITY_WORKSPACE_UI_VERSION


REQUIRED_CONTROL_IDS = {
    "feature-filter",
    "category-filters",
    "feature-list",
    "feature-count",
    "coverage",
    "feature-title",
    "feature-category",
    "feature-help",
    "classification",
    "fields",
    "approval-box",
    "approved",
    "destructive-wrap",
    "destructive-confirmed",
    "run",
    "cancel",
    "job-meta",
    "output",
    "output-state",
    "jobs-list",
    "refresh-jobs",
}


def test_security_workspace_is_reorganized_and_offline_safe() -> None:
    client = TestClient(create_app())
    page = client.get("/workbench")
    assert page.status_code == 200
    body = page.text

    assert 'class="global-rail"' in body
    assert 'class="workspace-grid"' in body
    assert 'class="panel jobs activity-panel"' in body
    assert "Security Workspace" in body
    assert "AI proposes." in body
    assert "Evidence proves." in body
    assert "Humans control." in body
    for control_id in REQUIRED_CONTROL_IDS:
        assert f'id="{control_id}"' in body

    assert "fonts.googleapis" not in body
    assert "fonts.gstatic" not in body
    assert "https://" not in body


def test_security_workspace_css_uses_professional_two_column_information_architecture() -> None:
    css = SECURITY_WORKSPACE_CSS
    assert '"Segoe UI Variable Text"' in css
    assert '"Cascadia Code"' in css
    assert "grid-template-columns: 236px minmax(0, 1fr)" in css
    assert "grid-template-columns: 300px minmax(0, 1fr)" in css
    assert ".activity-panel { grid-column: 1 / -1" in css
    assert "radial-gradient" not in css
    assert "#78c38d" not in css
    assert "fonts.googleapis" not in css
    assert "@import" not in css


def test_security_workspace_preserves_cli_web_and_execution_safety_contract() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/workbench/catalog")
    assert response.status_code == 200
    payload = response.json()

    assert payload["ui_version"] == SECURITY_WORKSPACE_UI_VERSION
    assert payload["contract"]["complete"] is True
    assert payload["contract"]["cli_commands"] == payload["contract"]["web_features"]
    assert payload["execution"] == {
        "backend": "web-console-fixed-runner",
        "shell": False,
        "arbitrary_executable": False,
        "user_supplied_argv": False,
        "mutations_require_approval": True,
    }


def test_security_workspace_assets_keep_restrictive_csp() -> None:
    client = TestClient(create_app())
    page = client.get("/workbench")
    css = client.get("/workbench/styles.css")
    script = client.get("/workbench/app.js")

    assert css.status_code == 200
    assert script.status_code == 200
    assert css.headers["content-type"].startswith("text/css")
    assert script.headers["content-type"].startswith("application/javascript")
    csp = page.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
