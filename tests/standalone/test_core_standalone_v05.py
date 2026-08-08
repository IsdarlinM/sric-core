from __future__ import annotations

import tomllib
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from sric.api_vnext import create_app
from sric.cli_all import app


ROOT = Path(__file__).resolve().parents[2]
runner = CliRunner()


def test_core_has_no_product_runtime_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    runtime = "\n".join(project["dependencies"]).lower()
    for product in ("reprosec", "authtwin", "fossilscope", "trustboundary", "exposuredna"):
        assert product not in runtime


def test_core_cli_safe_smokes() -> None:
    for args in (["version"], ["doctor", "--json"], ["capabilities"]):
        result = runner.invoke(app, list(args))
        assert result.exit_code == 0, f"{args}: {result.output}"


def test_core_capability_api() -> None:
    response = TestClient(create_app()).get("/api/v1/evidence-native/capabilities")
    assert response.status_code == 200
    assert response.json()["core_compatible"] is True
