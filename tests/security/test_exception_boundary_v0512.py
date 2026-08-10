from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sric.api import create_app
from sric.audit import AuditLogger
from sric.cli_style import CLIBrand, run_branded_cli
from sric.errors import safe_exception_message
from sric.redaction import redact_structure, redact_text


def test_safe_exception_message_redacts_secret_key_values_and_bearer_tokens() -> None:
    exc = RuntimeError(
        "request failed token=super-secret Authorization: Bearer abc.def.ghi password=hunter2"
    )
    message = safe_exception_message(exc)
    assert "super-secret" not in message
    assert "abc.def.ghi" not in message
    assert "hunter2" not in message
    assert "REDACTED" in message


def test_recursive_redaction_converts_metadata_to_json_safe_primitives() -> None:
    payload, detected = redact_structure(
        {
            "nested": {
                "access_token": "secret-token",
                "path": Path("evidence/item.json"),
                "message": "password=hidden-value",
            },
            "tuple": ("ok", 1),
        }
    )
    encoded = json.dumps(payload)
    assert "secret-token" not in encoded
    assert "hidden-value" not in encoded
    assert "evidence/item.json" in encoded
    assert detected


def test_audit_logger_redacts_result_and_nested_metadata(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    AuditLogger(path).write(
        user="tester",
        action="validate",
        target="https://example.test/path?token=query-secret",
        policy_decision="ALLOW",
        result="failed password=result-secret",
        tool_version="0.5.12-dev",
        metadata={"authorization": "Bearer metadata-secret", "nested": {"token": "deep-secret"}},
    )
    raw = path.read_text(encoding="utf-8")
    assert "query-secret" not in raw
    assert "result-secret" not in raw
    assert "metadata-secret" not in raw
    assert "deep-secret" not in raw
    assert "REDACTED" in raw


def test_api_value_errors_are_redacted() -> None:
    app = create_app()

    @app.get("/_test/secret-error")
    async def secret_error() -> None:
        raise ValueError("token=api-secret password=another-secret")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_test/secret-error")
    assert response.status_code == 400
    body = response.text
    assert "api-secret" not in body
    assert "another-secret" not in body
    assert "REDACTED" in body


def test_run_branded_cli_contains_unexpected_exception_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("SENTINEL_BANNER", "never")
    monkeypatch.delenv("SENTINEL_DEBUG", raising=False)
    monkeypatch.setattr(sys, "argv", ["example"])

    def failing_app() -> None:
        raise OSError("password=do-not-print")

    with pytest.raises(SystemExit) as raised:
        run_branded_cli(
            failing_app,
            CLIBrand("Example", "Exception boundary regression.", "0.0.0"),
        )
    captured = capsys.readouterr()
    assert raised.value.code == 1
    assert "Traceback" not in captured.err
    assert "do-not-print" not in captured.err
    assert "OSError" in captured.err
    assert "REDACTED" in captured.err


def test_run_branded_cli_preserves_debug_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SENTINEL_BANNER", "never")
    monkeypatch.setenv("SENTINEL_DEBUG", "1")
    monkeypatch.setattr(sys, "argv", ["example"])

    def failing_app() -> None:
        raise RuntimeError("debug-only")

    with pytest.raises(RuntimeError, match="debug-only"):
        run_branded_cli(
            failing_app,
            CLIBrand("Example", "Exception boundary regression.", "0.0.0"),
        )


def test_existing_text_redaction_still_handles_headers() -> None:
    result = redact_text("Authorization: Bearer abc123\nCookie: sid=value")
    assert "abc123" not in result.text
    assert "sid=value" not in result.text
