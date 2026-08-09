from __future__ import annotations

from typer.testing import CliRunner

from sric.cli_all import app
from sric.web_console import build_command_catalog
from sric.web_workbench import build_feature_catalog

runner = CliRunner()


def test_every_public_command_help_and_parameter_is_reachable() -> None:
    catalog = build_command_catalog("sric.cli_all")
    assert catalog

    root = runner.invoke(app, ["--help"])
    assert root.exit_code == 0, root.output

    for command in catalog:
        argv = command["path"].split() + ["--help"]
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, f"{' '.join(argv)}\n{result.output}"
        for param in command["params"]:
            if param["kind"] == "option":
                for opt in param["opts"]:
                    assert opt in result.output, f"{command['path']} missing {opt} in help"
            elif param["required"]:
                assert param["name"].replace("_", "-").lower() in result.output.lower().replace("_", "-")


def test_every_cli_argument_is_present_in_web_schema_in_original_order() -> None:
    cli = {item["path"]: item for item in build_command_catalog("sric.cli_all")}
    web = {item["path"]: item for item in build_feature_catalog("sric.cli_all")}
    assert set(cli) == set(web)
    for path in cli:
        assert [param["name"] for param in cli[path]["params"]] == [
            param["name"] for param in web[path]["params"]
        ]
        assert [param["required"] for param in cli[path]["params"]] == [
            param["required"] for param in web[path]["params"]
        ]
