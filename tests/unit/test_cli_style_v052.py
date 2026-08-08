from __future__ import annotations

import os

from typer.testing import CliRunner

from sric.cli_all import BRAND, app
from sric.cli_style import CLIBrand, build_banner, color_enabled, normalize_no_color_argv


def test_banner_contains_product_description_signature_and_version() -> None:
    banner = build_banner(BRAND)
    assert "SRIC Core" in banner
    assert "Evidence-native shared core" in banner
    assert "IsdarlinM :: v0.5.2" in banner
    assert "\x1b[" not in banner


def test_normalize_no_color_accepts_flag_after_subcommand() -> None:
    assert normalize_no_color_argv(["sric", "doctor", "--no-color", "--json"]) == [
        "sric",
        "--no-color",
        "doctor",
        "--json",
    ]


def test_no_color_option_is_documented_on_root_help() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--no-color" in result.stdout


def test_no_color_respects_environment_without_mutating_plain_banner(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled() is False
    brand = CLIBrand("Example", "Example description.", "1.2.3")
    assert "IsdarlinM :: v1.2.3" in build_banner(brand)
    assert os.environ["NO_COLOR"] == "1"
