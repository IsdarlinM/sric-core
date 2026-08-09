from __future__ import annotations

import pytest

from sric.web_console import (
    ConsoleRunRequest,
    WebConsoleConfig,
    WebConsoleManager,
    build_command_catalog,
    redact_argv,
)


def _by_path() -> dict[str, dict[str, object]]:
    return {item["path"]: item for item in build_command_catalog("sric.cli_all")}


def test_catalog_discovers_real_root_and_nested_cli_commands() -> None:
    commands = _by_path()
    assert "doctor" in commands
    assert "update" in commands
    assert "web" in commands
    assert any(path.startswith("workspace ") for path in commands)


def test_catalog_marks_mutation_and_web_context_only() -> None:
    commands = _by_path()
    assert commands["update"]["classification"] == "MUTATING_REVERSIBLE"
    assert commands["update"]["approval_required"] is True
    assert commands["web"]["context_only"] is True
    assert commands["web"]["executable"] is False


def test_cli_argument_redaction_covers_separate_and_inline_secrets() -> None:
    redacted = redact_argv(
        ["--token", "secret-value", "--api-key=another-secret", "workspace"]
    )
    assert "secret-value" not in redacted
    assert not any("another-secret" in item for item in redacted)
    assert redacted[-1] == "workspace"


def test_manager_requires_approval_before_mutating_commands() -> None:
    manager = WebConsoleManager(
        WebConsoleConfig(
            product="sric-core",
            display_name="SRIC Core",
            cli_module="sric.cli_all",
            version="0.5.4",
        )
    )
    with pytest.raises(PermissionError, match="explicit approval"):
        manager.submit(ConsoleRunRequest(command="update"))


def test_manager_never_starts_nested_web_server() -> None:
    manager = WebConsoleManager(
        WebConsoleConfig(
            product="sric-core",
            display_name="SRIC Core",
            cli_module="sric.cli_all",
            version="0.5.4",
        )
    )
    with pytest.raises(RuntimeError, match="already running"):
        manager.submit(ConsoleRunRequest(command="web"))
