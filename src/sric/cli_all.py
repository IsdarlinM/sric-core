from __future__ import annotations

from .cli_vnext import app, run as _run
from . import cli_capabilities as _cli_capabilities  # noqa: F401

__all__ = ["app", "run"]


def run() -> None:
    """Run the complete SRIC CLI including standalone capability discovery."""

    _run()
