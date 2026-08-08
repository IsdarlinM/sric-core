from __future__ import annotations

import os

from typer.main import get_command

from sric.cli_all import BRAND, app
from sric.cli_style import CLIBrand, build_banner, color_enabled, normalize_no_color_argv


def test_banner_contains_product_description_signature_and_version() -> None:
    banner = build_banner(BRAND)
    assert "SRIC Core" in banner
    assert "Evidence-native shared core" in banner
    assert "IsdarlinM :: v0.5.2" in banner
    assert "\x1b[" not in banner


def test_banner_wraps_long_descriptions_without_truncation() -> None:
    description = "A deliberately long description that remains readable instead of breaking the CLI banner layout on narrow terminals."
    banner = build_banner(CLIBrand("Example", description, "1.2.3"), width=64)
    assert "deliberately long description" in banner
    assert "breaking the CLI banner" in banner
    assert "IsdarlinM :: v1.2.3" in banner


def test_normalize_no_color_accepts_flag_after_subcommand() -> None:
    assert normalize_no_color_argv(["sric", "doctor", "--no-color", "--json"]) == [
        "sric",
        "--no-color",
        "doctor",
        "--json",
    ]


def test_no_color_option_is_registered_on_root_command() -> None:
    command = get_command(app)
    assert any("--no-color" in getattr(param, "opts", ()) for param in command.params)


def test_no_color_respects_environment_without_mutating_plain_banner(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert color_enabled() is False
    brand = CLIBrand("Example", "Example description.", "1.2.3")
    assert "IsdarlinM :: v1.2.3" in build_banner(brand)
    assert os.environ["NO_COLOR"] == "1"
