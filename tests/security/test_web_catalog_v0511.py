from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

import typer
from fastapi.testclient import TestClient

from sric.api import create_app
from sric.web_catalog import build_json_safe_command_catalog


class Mode(Enum):
    PASSIVE = "passive"


def test_real_sric_console_catalog_is_http_json() -> None:
    client = TestClient(create_app())
    response = client.get("/api/v1/console/catalog")
    assert response.status_code == 200
    payload = response.json()
    assert payload["product"] == "sric-core"
    assert payload["commands"]
    json.dumps(payload, allow_nan=False)


def test_catalog_coerces_non_json_defaults_and_metadata(monkeypatch) -> None:
    app = typer.Typer()

    @app.command()
    def sample(
        root: Path = typer.Option(Path("demo"), "--root"),
        mode: Mode = typer.Option(Mode.PASSIVE, "--mode"),
        labels: list[str] = typer.Option([], "--label"),
    ) -> None:
        pass

    class Module:
        pass

    module = Module()
    module.app = app

    import sric.web_catalog as catalog_module

    real_import = catalog_module.importlib.import_module

    def fake_import(name: str):
        return module if name == "sentinel_test_cli" else real_import(name)

    monkeypatch.setattr(catalog_module.importlib, "import_module", fake_import)
    catalog = build_json_safe_command_catalog("sentinel_test_cli")
    json.dumps(catalog, allow_nan=False)
    command = next(item for item in catalog if item["path"] == "sample")
    defaults = {param["name"]: param["default"] for param in command["params"]}
    assert defaults["root"] == "demo"
    assert defaults["mode"] == "passive"
    assert defaults["labels"] == []
