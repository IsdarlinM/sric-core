from __future__ import annotations

import typer

from . import __version__
from . import cli as _base_cli
from . import cli_capabilities as _cli_capabilities  # noqa: F401
from .cli_style import CLIBrand, configure_cli_context, no_color_option, run_branded_cli
from .cli_vnext import _normalize_trailing_help, app
from . import cli_update as _cli_update  # noqa: F401,E402

__all__ = ["BRAND", "app", "run"]

BRAND = CLIBrand(
    product="SRIC Core",
    description="Evidence-native shared core for security research intelligence.",
    version=__version__,
)

_original_main = _base_cli.main
app.rich_markup_mode = "rich"


@app.callback(invoke_without_command=True)
def branded_main(
    ctx: typer.Context,
    no_color: bool = no_color_option(),
) -> None:
    """SRIC Core CLI with shared Sentinel Forge presentation controls."""

    configure_cli_context(ctx, no_color=no_color)
    _original_main(ctx)


def run() -> None:
    """Run the complete SRIC CLI with branded, script-safe terminal presentation."""

    run_branded_cli(app, BRAND, argv_normalizer=_normalize_trailing_help)
