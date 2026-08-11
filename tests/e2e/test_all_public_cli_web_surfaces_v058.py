from __future__ import annotations

from typer.testing import CliRunner

from sric.cli_all import app, normalize_help_argv
from sric.web_console import build_command_catalog
from sric.web_workbench import build_feature_catalog, feature_contract


def test_root_help_alias_and_standard_help_flags() -> None:
    runner = CliRunner()
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["-h"]).exit_code == 0
    normalized = normalize_help_argv(["sric", "help"])
    assert normalized == ["sric", "--help"]
    assert runner.invoke(app, normalized[1:]).exit_code == 0


def test_every_public_command_has_both_help_flags_trailing_help_and_web_params() -> None:
    cli = build_command_catalog("sric.cli_all")
    web = build_feature_catalog("sric.cli_all")
    contract = feature_contract("sric.cli_all")
    assert contract["complete"] is True
    assert contract["cli_commands"] == contract["web_features"]

    cli_by_path = {item["path"]: item for item in cli}
    web_by_path = {item["path"]: item for item in web}
    assert set(cli_by_path) == set(web_by_path)

    runner = CliRunner()
    for path, command in cli_by_path.items():
        parts = path.split()
        assert runner.invoke(app, [*parts, "--help"]).exit_code == 0, path
        assert runner.invoke(app, [*parts, "-h"]).exit_code == 0, path
        if parts == ["help"]:
            continue
        normalized = normalize_help_argv(["sric", *parts, "help"])
        assert normalized[-1] == "--help", path
        assert runner.invoke(app, normalized[1:]).exit_code == 0, path
        assert [p["name"] for p in command["params"]] == [p["name"] for p in web_by_path[path]["params"]]
