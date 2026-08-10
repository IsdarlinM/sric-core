from __future__ import annotations

import json

import pytest
import typer
from fastapi import HTTPException
from typer.main import get_command

from sric import web_workbench
from sric.web_catalog import (
    _classify_catalog_command,
    _option_metadata,
    install_json_safe_catalog,
)
from sric.web_console import ConsoleRunRequest, WebConsoleConfig, WebConsoleManager
from sric.web_guardrails import SUPPORTED_WEB_CONTROLS, WORKBENCH_RECOVERY_JS


def test_real_typer_argument_is_json_safe_and_keeps_argument_semantics() -> None:
    app = typer.Typer()

    @app.command()
    def sample(target: str = typer.Argument(..., help="Target value")) -> None:
        pass

    root = get_command(app)
    command = root.commands["sample"] if hasattr(root, "commands") else root
    param = command.params[0]
    payload = _option_metadata(param)

    assert type(param).__name__ == "TyperArgument"
    assert payload["kind"] == "argument"
    assert payload["name"] == "target"
    assert payload["required"] is True
    assert payload["help"] == "Target value"
    json.dumps(payload, allow_nan=False)


def test_known_writer_commands_fail_closed_as_mutating_reversible() -> None:
    for name in ("collect", "collect-url", "demo", "evidence", "extract", "report", "validate"):
        classification, approval_required, context_only = _classify_catalog_command((name,))
        assert classification == "MUTATING_REVERSIBLE", name
        assert approval_required is True, name
        assert context_only is False, name


def test_every_sric_cli_parameter_has_a_supported_render_control() -> None:
    install_json_safe_catalog()
    features = web_workbench.build_feature_catalog("sric.cli_all")
    assert features
    for feature in features:
        assert feature["id"]
        assert feature["path"]
        for param in feature["params"]:
            assert param["id"]
            assert param["name"]
            assert param["control"] in SUPPORTED_WEB_CONTROLS
            if param["kind"] == "option":
                assert param["primary_opt"]


def test_unexpected_feature_catalog_exception_becomes_redacted_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_json_safe_catalog()

    def fail_catalog(_module: str) -> list[dict[str, object]]:
        raise RuntimeError("password=do-not-display")

    monkeypatch.setattr(web_workbench, "build_command_catalog", fail_catalog)
    with pytest.raises(HTTPException) as exc_info:
        web_workbench.build_feature_catalog("sric.cli_all")
    assert exc_info.value.status_code == 503
    detail = str(exc_info.value.detail)
    assert "Security Workspace catalog unavailable" in detail
    assert "do-not-display" not in detail


def test_unexpected_submission_exception_becomes_redacted_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_json_safe_catalog()
    manager = WebConsoleManager(
        WebConsoleConfig(
            product="sric-core",
            display_name="SRIC",
            cli_module="sric.cli_all",
            version="0.5.16",
        )
    )

    def fail_catalog(_path: str) -> dict[str, object]:
        raise OSError("token=super-secret-value")

    monkeypatch.setattr(manager, "_catalog_item", fail_catalog)
    with pytest.raises(HTTPException) as exc_info:
        manager.submit(ConsoleRunRequest(command="doctor"))
    assert exc_info.value.status_code == 503
    detail = str(exc_info.value.detail)
    assert "operation submission unavailable" in detail
    assert "super-secret-value" not in detail


def test_event_stream_runtime_exception_is_terminal_and_does_not_escape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_json_safe_catalog()
    manager = WebConsoleManager(
        WebConsoleConfig(
            product="sric-core",
            display_name="SRIC",
            cli_module="sric.cli_all",
            version="0.5.16",
        )
    )

    # The hardened implementation calls the retired/current lookup helper. Making its
    # job store structurally invalid reproduces an unexpected internal runtime failure.
    monkeypatch.setattr(manager, "_jobs", None)
    chunks, cursor, status = manager.output_since("job", 7)
    assert status == "failed"
    assert cursor == 7
    assert chunks
    assert "event stream unavailable" in chunks[0].lower()


def test_recovery_javascript_exposes_real_reload_and_promise_error_handling() -> None:
    install_json_safe_catalog()
    script = web_workbench.WORKBENCH_JS
    assert "Reload interface" in script
    assert "window.location.reload()" in script
    assert 'addEventListener("unhandledrejection"' in script
    assert 'addEventListener("error"' in script
    assert "Capability catalog did not become available" in script
    assert WORKBENCH_RECOVERY_JS in script
