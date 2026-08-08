from __future__ import annotations

import json

import typer

from .capabilities import discover_capabilities
from .cli_vnext import app


@app.command("capabilities")
def capabilities_command(
    product: str | None = typer.Option(None, "--product", help="Evaluate standalone readiness for one product."),
) -> None:
    """Discover installed Sentinel Forge products and optional capabilities."""

    report = discover_capabilities(current_product=product)
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2))
    if product is not None and not report.standalone_ready:
        raise typer.Exit(2)
