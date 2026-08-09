from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .cli import app
from .updater import perform_update


@app.command("update")
def update(
    check: bool = typer.Option(
        False, "--check", help="Verify signed release metadata and report availability only."
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Install the selected signed release even when that same version is already installed. Never downgrades.",
    ),
    manifest: Optional[str] = typer.Option(
        None, "--manifest", help="Signed release manifest path or HTTPS URL."
    ),
    public_key: Optional[Path] = typer.Option(
        None, "--public-key", help="Trusted Ed25519 release public key."
    ),
) -> None:
    """Check/install a signed wheel release, with explicit same-version force reinstall support."""

    if check and force:
        typer.echo("--check and --force cannot be used together.", err=True)
        raise typer.Exit(2)

    source = manifest or os.getenv("SRIC_RELEASE_MANIFEST_URL")
    key = public_key or (
        Path(os.environ["SRIC_RELEASE_PUBLIC_KEY"])
        if os.getenv("SRIC_RELEASE_PUBLIC_KEY")
        else None
    )
    if not source or key is None:
        typer.echo(
            "No trusted release channel configured. Provide --manifest and --public-key, "
            "or SRIC_RELEASE_MANIFEST_URL/SRIC_RELEASE_PUBLIC_KEY.",
            err=True,
        )
        raise typer.Exit(2)
    try:
        status = perform_update(
            manifest_source=source,
            public_key_path=key,
            expected_product="sric-core",
            current_version=__version__,
            check_only=check,
            force=force,
        )
    except Exception as exc:
        typer.echo(f"Update verification failed; no update was installed: {exc}", err=True)
        raise typer.Exit(6)
    typer.echo(json.dumps(status.__dict__, indent=2))
