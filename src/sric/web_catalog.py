from __future__ import annotations

import html
import importlib
import json
import math
import sys
from enum import Enum
from pathlib import Path
from typing import Any

import click
from typer.main import get_command


CONSERVATIVE_MUTATING_COMMAND_NAMES = {
    "collect",
    "collect-url",
    "demo",
    "evidence",
    "extract",
    "jobs",
    "notebook",
    "report",
    "validate",
    "workspace",
}
READ_ONLY_WORKSPACE_ACTIONS = {"list", "show", "status"}


def _json_value(value: Any) -> Any:
    """Return deterministic JSON-safe metadata without executing user objects."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_json_value(item) for item in value]
    return repr(value)


def _safe_nargs(param: Any) -> int:
    value = getattr(param, "nargs", 1)
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return 1


def _safe_choices(param_type: Any) -> list[Any]:
    raw = getattr(param_type, "choices", None)
    if raw is None:
        return []
    try:
        return [_json_value(item) for item in raw]
    except TypeError:
        return []


def _numeric_bound(param_type: Any, name: str) -> Any:
    value = getattr(param_type, name, None)
    if value is None:
        return None
    return _json_value(value)


def _base_parameter_metadata(param: Any) -> dict[str, Any]:
    param_type = getattr(param, "type", None)
    type_name = getattr(param_type, "name", None)
    if not isinstance(type_name, str) or not type_name:
        type_name = type(param_type).__name__ if param_type is not None else "text"
    return {
        "name": str(getattr(param, "name", "") or ""),
        "required": bool(getattr(param, "required", False)),
        "multiple": bool(getattr(param, "multiple", False)),
        "nargs": _safe_nargs(param),
        "default": _json_value(getattr(param, "default", None)),
        "type": str(type_name),
        "choices": _safe_choices(param_type),
        "min": _numeric_bound(param_type, "min"),
        "max": _numeric_bound(param_type, "max"),
        "clamp": bool(getattr(param_type, "clamp", False)),
        "path": {
            "exists": bool(getattr(param_type, "exists", False)),
            "file_okay": bool(getattr(param_type, "file_okay", False)),
            "dir_okay": bool(getattr(param_type, "dir_okay", False)),
            "writable": bool(getattr(param_type, "writable", False)),
            "readable": bool(getattr(param_type, "readable", True)),
        }
        if str(type_name).lower() == "path" or type(param_type).__name__.lower() == "path"
        else None,
    }


def _parameter_kind(param: Any) -> str:
    """Identify modern Typer parameters without relying on Click subclass identity.

    Typer 0.26's TyperArgument/TyperOption derive from an abstraction rather than
    click.Argument/click.Option. Both expose ``opts``; treating every object with opts as
    an option therefore corrupts positional argument semantics. ``param_type_name`` is
    the primary contract, followed by conservative structural fallbacks.
    """
    hint = str(getattr(param, "param_type_name", "") or "").lower()
    if hint in {"argument", "option"}:
        return hint
    if isinstance(param, click.Argument):
        return "argument"
    if isinstance(param, click.Option):
        return "option"
    class_name = type(param).__name__.lower()
    if class_name.endswith("argument"):
        return "argument"
    if class_name.endswith("option"):
        return "option"
    opts = [str(item) for item in (getattr(param, "opts", ()) or ())]
    if any(item.startswith("-") for item in opts):
        return "option"
    return "argument"


def _option_metadata(param: Any) -> dict[str, Any]:
    """Serialize Click/Typer parameters without letting one unknown subtype break the catalog."""
    payload = _base_parameter_metadata(param)
    help_text = str(getattr(param, "help", "") or "")
    kind = _parameter_kind(param)
    payload["parameter_class"] = type(param).__name__
    if kind == "option":
        payload.update(
            {
                "kind": "option",
                "opts": [str(item) for item in (getattr(param, "opts", ()) or ())],
                "secondary_opts": [
                    str(item) for item in (getattr(param, "secondary_opts", ()) or ())
                ],
                "help": help_text,
                "is_flag": bool(getattr(param, "is_flag", False)),
                "count": bool(getattr(param, "count", False)),
            }
        )
        return payload
    payload.update(
        {"kind": "argument", "opts": [], "secondary_opts": [], "help": help_text}
    )
    return payload


def _classify_catalog_command(path: tuple[str, ...]) -> tuple[str, bool, bool]:
    """Apply the shared classifier plus conservative fail-closed Web overrides."""
    from .web_console import _classify_command

    classification, approval_required, context_only = _classify_command(path)
    normalized = tuple(part.lower().replace("_", "-") for part in path)
    names = set(normalized)

    if "workspace" in names:
        if len(normalized) > 1 and normalized[-1] in READ_ONLY_WORKSPACE_ACTIONS:
            return classification, approval_required, context_only
        return "MUTATING_REVERSIBLE", True, context_only

    if names & CONSERVATIVE_MUTATING_COMMAND_NAMES:
        return "MUTATING_REVERSIBLE", True, context_only
    return classification, approval_required, context_only


def build_json_safe_command_catalog(cli_module: str) -> list[dict[str, Any]]:
    """Build the exact public Typer tree using only JSON-safe primitive metadata."""
    module = importlib.import_module(cli_module)
    app = getattr(module, "app", None)
    if app is None:
        raise RuntimeError(f"{cli_module} does not expose a Typer app")
    root = get_command(app)

    commands: list[dict[str, Any]] = []
    active: set[int] = set()

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        identity = id(command)
        if identity in active:
            raise RuntimeError(
                f"cyclic CLI command tree detected at {' '.join(prefix) or '<root>'}"
            )
        active.add(identity)
        try:
            children = getattr(command, "commands", None)
            if not isinstance(children, dict):
                return
            for raw_name, child in sorted(children.items(), key=lambda item: str(item[0])):
                if getattr(child, "hidden", False):
                    continue
                name = str(raw_name)
                path = prefix + (name,)
                classification, approval_required, context_only = _classify_catalog_command(path)
                raw_help = (
                    getattr(child, "help", None)
                    or getattr(child, "short_help", None)
                    or ""
                )
                raw_params = getattr(child, "params", ()) or ()
                commands.append(
                    {
                        "path": " ".join(path),
                        "help": str(raw_help),
                        "classification": str(classification),
                        "approval_required": bool(approval_required),
                        "approval_phrase_required": classification
                        == "MUTATING_DESTRUCTIVE",
                        "context_only": bool(context_only),
                        "executable": not bool(context_only),
                        "is_group": isinstance(getattr(child, "commands", None), dict),
                        "params": [_option_metadata(param) for param in raw_params],
                    }
                )
                walk(child, path)
        finally:
            active.remove(identity)

    root_children = getattr(root, "commands", None)
    if isinstance(root_children, dict):
        walk(root, ())
    else:
        # Typer collapses an application containing a single command into a
        # TyperCommand. Preserve that public command in the Web catalog instead
        # of returning an empty interface.
        name = str(getattr(root, "name", "") or "").strip()
        if name:
            classification, approval_required, context_only = _classify_catalog_command((name,))
            raw_help = getattr(root, "help", None) or getattr(root, "short_help", None) or ""
            commands.append(
                {
                    "path": name,
                    "help": str(raw_help),
                    "classification": str(classification),
                    "approval_required": bool(approval_required),
                    "approval_phrase_required": classification == "MUTATING_DESTRUCTIVE",
                    "context_only": bool(context_only),
                    "executable": not bool(context_only),
                    "is_group": False,
                    "params": [
                        _option_metadata(param)
                        for param in (getattr(root, "params", ()) or ())
                    ],
                }
            )
    json.dumps(commands, ensure_ascii=False, allow_nan=False)
    return commands


def _guided_console_alias(config: Any, csrf_token: str) -> str:
    """Keep the historical route as a safe alias without exposing command/argv input."""
    display_name = html.escape(str(config.display_name))
    token = html.escape(csrf_token, quote=True)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="sentinel-console-token" content="{token}">
<meta http-equiv="refresh" content="0;url=/workbench">
<title>{display_name} Security Console</title>
<link rel="stylesheet" href="/console/styles.css">
</head>
<body>
<main class="guided-alias">
<h1>{display_name} Security Console</h1>
<p>The command-oriented console has been retired. Opening the guided operations interface.</p>
<a href="/workbench">Open Security Console</a>
</main>
<script src="/console/app.js" defer></script>
</body>
</html>"""


def install_json_safe_catalog() -> None:
    """Install JSON-safe metadata, guided-console aliasing, and runtime hardening."""
    from . import web_console
    from .web_guardrails import install_web_surface_guardrails
    from .web_runtime import install_web_console_runtime_hardening

    web_console.build_command_catalog = build_json_safe_command_catalog
    web_console._console_html = _guided_console_alias
    web_console.CONSOLE_CSS = (
        "body{margin:0;min-height:100vh;display:grid;place-items:center;"
        "background:#0b0f14;color:#e7edf3;font-family:\"Segoe UI Variable Text\","
        "\"Segoe UI Variable\",Aptos,system-ui,sans-serif}"
        ".guided-alias{max-width:42rem;padding:2rem}a{color:#70bdca}"
    )
    web_console.CONSOLE_JS = 'window.location.replace("/workbench");'
    install_web_console_runtime_hardening()
    workbench = sys.modules.get("sric.web_workbench")
    if workbench is not None:
        setattr(workbench, "build_command_catalog", build_json_safe_command_catalog)
    install_web_surface_guardrails()
