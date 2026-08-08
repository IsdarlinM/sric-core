from __future__ import annotations

import os
import sys
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import typer


@dataclass(frozen=True, slots=True)
class CLIBrand:
    """Human-facing CLI identity shared by Sentinel Forge products."""

    product: str
    description: str
    version: str
    signature: str = "IsdarlinM"

    @property
    def signature_line(self) -> str:
        return f"{self.signature} :: v{self.version}"


def build_banner(brand: CLIBrand, *, width: int = 76) -> str:
    """Build a portable ASCII banner without ANSI escape sequences."""

    width = max(64, min(width, 96))
    inner = width - 2
    lines = [
        "SENTINEL FORGE",
        brand.product,
        brand.description,
        brand.signature_line,
    ]
    if any(len(line) > inner - 2 for line in lines):
        raise ValueError("CLI brand text is too long for the configured banner width")
    top = "+" + "-" * inner + "+"
    body = [f"| {line:<{inner - 2}} |" for line in lines]
    return "\n".join([top, *body, top])


def no_color_option() -> Any:
    """Return the shared global --no-color Typer option."""

    return typer.Option(
        False,
        "--no-color",
        help="Disable ANSI/Rich colors while preserving normal command output.",
        is_eager=True,
        callback=_no_color_callback,
    )


def _no_color_callback(ctx: typer.Context, _param: object, value: bool) -> bool:
    if value:
        ctx.color = False
        ctx.meta["sentinel_no_color"] = True
    return value


def configure_cli_context(ctx: typer.Context, *, no_color: bool) -> None:
    """Apply color policy to an already-created Click/Typer context."""

    if no_color or "NO_COLOR" in os.environ:
        ctx.color = False
        ctx.meta["sentinel_no_color"] = True


def normalize_no_color_argv(argv: Sequence[str]) -> list[str]:
    """Treat --no-color as a global flag even when typed after a subcommand."""

    normalized = list(argv)
    if len(normalized) <= 1 or "--no-color" not in normalized[1:]:
        return normalized
    tail = [arg for arg in normalized[1:] if arg != "--no-color"]
    return [normalized[0], "--no-color", *tail]


def color_enabled(*, no_color: bool = False) -> bool:
    return not no_color and "NO_COLOR" not in os.environ


def should_show_banner() -> bool:
    """Show banners on interactive terminals while keeping redirected stdout clean."""

    mode = os.getenv("SENTINEL_BANNER", "auto").strip().lower()
    if mode in {"0", "false", "off", "never"}:
        return False
    if mode in {"1", "true", "on", "always"}:
        return True
    return bool(getattr(sys.stderr, "isatty", lambda: False)())


def render_banner(brand: CLIBrand, *, no_color: bool = False) -> None:
    """Render a subdued green banner to stderr so stdout remains script-friendly."""

    if not should_show_banner():
        return
    enabled = color_enabled(no_color=no_color)
    typer.secho(
        build_banner(brand),
        fg=typer.colors.GREEN if enabled else None,
        dim=enabled,
        err=True,
        color=enabled,
    )


@contextmanager
def color_environment(*, no_color: bool) -> Iterator[None]:
    """Temporarily expose NO_COLOR so Rich help follows the global option."""

    previous = os.environ.get("NO_COLOR")
    if no_color:
        os.environ["NO_COLOR"] = "1"
    try:
        yield
    finally:
        if no_color:
            if previous is None:
                os.environ.pop("NO_COLOR", None)
            else:
                os.environ["NO_COLOR"] = previous


def run_branded_cli(
    app: Callable[[], None],
    brand: CLIBrand,
    *,
    argv_normalizer: Callable[[list[str]], list[str]] | None = None,
) -> None:
    """Run a Sentinel Forge CLI with global color normalization and branded banner."""

    prepared = normalize_no_color_argv(sys.argv)
    if argv_normalizer is not None:
        prepared = argv_normalizer(prepared)
    sys.argv[:] = prepared
    no_color = "--no-color" in prepared[1:] or "NO_COLOR" in os.environ
    with color_environment(no_color=no_color):
        render_banner(brand, no_color=no_color)
        app()
