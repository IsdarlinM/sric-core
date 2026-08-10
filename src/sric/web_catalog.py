from __future__ import annotations

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
    # Fail here, close to the source, rather than as an opaque FastAPI response serialization 500.
    json.dumps(commands, ensure_ascii=False, allow_nan=False)
    return commands


def install_json_safe_catalog() -> None:
    """Install the hardened catalog builder for console and already-imported Workbench code."""
    from . import web_console

    web_console.build_command_catalog = build_json_safe_command_catalog
    workbench = sys.modules.get("sric.web_workbench")
    if workbench is not None:
        setattr(workbench, "build_command_catalog", build_json_safe_command_catalog)
