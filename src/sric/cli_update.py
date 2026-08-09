from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .cli import app
from .updater import perform_product_update


@app.command("update")
def update(
    check: bool = typer.Option(
        False, "--check", help="Check the official release channel and report availability only."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Reinstall the official release even when that same version is already installed. Never downgrades.",
    ),
    manifest: Optional[str] = typer.Option(
        None,
        "--manifest",
        help="Advanced override: custom signed release manifest path or HTTPS URL.",
    ),
    public_key: Optional[Path] = typer.Option(
        None,
        "--public-key",
        help="Advanced override: trusted Ed25519 public key for a custom manifest.",
    ),
) -> None:
    """Check/install from the official zero-config channel or an explicit custom channel."""

    if check and force:
        typer.echo("--check and --force cannot be used together.", err=True)
        raise typer.Exit(2)

    try:
        status = perform_product_update(
            expected_product="sric-core",
            current_version=__version__,
            check_only=check,
            force=force,
            manifest_source=manifest,
            public_key_path=public_key,
            manifest_env="SRIC_RELEASE_MANIFEST_URL",
            public_key_env="SRIC_RELEASE_PUBLIC_KEY",
        )
    except Exception as exc:
        typer.echo(f"Update verification failed; no update was installed: {exc}", err=True)
        raise typer.Exit(6)
    typer.echo(json.dumps(status.__dict__, indent=2))
