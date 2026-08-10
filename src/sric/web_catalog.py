from __future__ import annotations

import html
import importlib
import json
import math
import sys
from enum import Enum
from pathlib import Path
from typing import Any

from typer.main import get_command


def _json_value(value: Any) -> Any:
    """Return deterministic JSON-safe metadata without executing user objects."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Path):
        return str(value)
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


def _option_metadata(param: Any) -> dict[str, Any]:
    param_type = getattr(param, "type", None)
    type_name = getattr(param_type, "name", None)
    if not isinstance(type_name, str) or not type_name:
        type_name = type(param_type).__name__ if param_type is not None else "text"

    payload: dict[str, Any] = {
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
        if type_name.lower() == "path" or type(param_type).__name__.lower() == "path"
        else None,
    }
    if hasattr(param, "opts"):
        payload.update(
            {
                "kind": "option",
                "opts": [str(item) for item in (getattr(param, "opts", ()) or ())],
                "secondary_opts": [
                    str(item) for item in (getattr(param, "secondary_opts", ()) or ())
                ],
                "help": str(getattr(param, "help", "") or ""),
                "is_flag": bool(getattr(param, "is_flag", False)),
                "count": bool(getattr(param, "count", False)),
            }
        )
    else:
        payload.update(
            {"kind": "argument", "opts": [], "secondary_opts": [], "help": ""}
        )
    return payload


def build_json_safe_command_catalog(cli_module: str) -> list[dict[str, Any]]:
    """Build the exact public Typer tree using only JSON-safe primitive metadata."""
    module = importlib.import_module(cli_module)
    app = getattr(module, "app", None)
    if app is None:
        raise RuntimeError(f"{cli_module} does not expose a Typer app")
    root = get_command(app)

    # Import classification only after web_console is loaded to keep this helper acyclic.
    from .web_console import _classify_command

    commands: list[dict[str, Any]] = []
    active: set[int] = set()

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        identity = id(command)
        if identity in active:
            raise RuntimeError(f"cyclic CLI command tree detected at {' '.join(prefix) or '<root>'}")
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
                classification, approval_required, context_only = _classify_command(path)
                raw_help = getattr(child, "help", None) or getattr(child, "short_help", None) or ""
                raw_params = getattr(child, "params", ()) or ()
                commands.append(
                    {
                        "path": " ".join(path),
                        "help": str(raw_help),
                        "classification": str(classification),
                        "approval_required": bool(approval_required),
                        "approval_phrase_required": classification == "MUTATING_DESTRUCTIVE",
                        "context_only": bool(context_only),
                        "executable": not bool(context_only),
                        "is_group": isinstance(getattr(child, "commands", None), dict),
                        "params": [_option_metadata(param) for param in raw_params],
                    }
                )
                walk(child, path)
        finally:
            active.remove(identity)

    walk(root, ())
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
    from .web_runtime import install_web_console_runtime_hardening

    web_console.build_command_catalog = build_json_safe_command_catalog
    web_console._console_html = _guided_console_alias
    web_console.CONSOLE_CSS = (
        "body{margin:0;min-height:100vh;display:grid;place-items:center;"
        "background:#090d0b;color:#e8f0eb;font-family:system-ui,sans-serif}"
        ".guided-alias{max-width:42rem;padding:2rem}a{color:#9fe1b0}"
    )
    web_console.CONSOLE_JS = 'window.location.replace("/workbench");'
    install_web_console_runtime_hardening()
    workbench = sys.modules.get("sric.web_workbench")
    if workbench is not None:
        setattr(workbench, "build_command_catalog", build_json_safe_command_catalog)
