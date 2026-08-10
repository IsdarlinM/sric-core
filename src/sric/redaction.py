from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "id_token",
    "client_secret",
    "client_assertion",
    "password",
    "passwd",
    "pwd",
    "session",
    "session_id",
    "sid",
    "api_key",
    "apikey",
    "x-api-key",
    "authorization",
    "cookie",
    "set-cookie",
    "private_key",
    "secret",
    "token",
}

DEFAULT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("authorization", re.compile(r"(?im)^(authorization\s*:\s*)(.+)$")),
    ("cookie", re.compile(r"(?im)^(cookie\s*:\s*)(.+)$")),
    ("set-cookie", re.compile(r"(?im)^(set-cookie\s*:\s*)(.+)$")),
    ("api-key", re.compile(r"(?i)(\b(?:api[_-]?key|x-api-key)\b\s*[:=]\s*)([^\s,;&]+)")),
    (
        "secret-kv",
        re.compile(
            r"(?i)(\b(?:access[_-]?token|refresh[_-]?token|id[_-]?token|client[_-]?secret|client[_-]?assertion|password|passwd|pwd|session(?:_id)?|sid|private[_-]?key|secret|token)\b\s*[:=]\s*)([^\s,;&]+)"
        ),
    ),
    ("bearer", re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")),
)


@dataclass(frozen=True)
class RedactionResult:
    text: str
    detected: dict[str, int]


def _token(name: str, index: int) -> str:
    safe = re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_") or "SECRET"
    return f"${{{{REDACTED_{safe}_{index}}}}}"


def _merge(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] = target.get(key, 0) + value


def redact_text(value: str) -> RedactionResult:
    detected: dict[str, int] = {}
    out = value
    for name, pattern in DEFAULT_PATTERNS:
        count = 0

        def repl(match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            prefix = match.group(1) if match.lastindex else ""
            return f"{prefix}{_token(name, count)}"

        out = pattern.sub(repl, out)
        if count:
            detected[name] = count
    return RedactionResult(out, detected)


def redact_url(value: str) -> RedactionResult:
    """Redact sensitive query parameters while preserving URL structure."""
    parsed = urlsplit(value)
    if not parsed.query:
        return RedactionResult(value, {})
    detected: dict[str, int] = {}
    counters: dict[str, int] = {}
    items: list[tuple[str, str]] = []
    for key, raw in parse_qsl(parsed.query, keep_blank_values=True):
        normalized = key.strip().lower()
        if normalized in SENSITIVE_KEYS or any(
            marker in normalized for marker in ("token", "secret", "password", "passwd", "api_key")
        ):
            counters[normalized] = counters.get(normalized, 0) + 1
            detected[normalized] = detected.get(normalized, 0) + 1
            items.append((key, _token(normalized, counters[normalized])))
        else:
            items.append((key, raw))
    query = urlencode(items, doseq=True, safe="${}")
    return RedactionResult(urlunsplit(parsed._replace(query=query)), detected)


def _redact_json_value(value: Any, detected: dict[str, int], counters: dict[str, int]) -> Any:
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, child in value.items():
            normalized = str(key).strip().lower()
            sensitive = normalized in SENSITIVE_KEYS or any(
                marker in normalized
                for marker in ("token", "secret", "password", "passwd", "api_key", "private_key")
            )
            if sensitive and child not in (None, ""):
                counters[normalized] = counters.get(normalized, 0) + 1
                detected[normalized] = detected.get(normalized, 0) + 1
                output[str(key)] = _token(normalized, counters[normalized])
            else:
                output[str(key)] = _redact_json_value(child, detected, counters)
        return output
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_redact_json_value(v, detected, counters) for v in value]
    if isinstance(value, str):
        result = redact_text(value)
        _merge(detected, result.detected)
        return result.text
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    result = redact_text(repr(value))
    _merge(detected, result.detected)
    return result.text


def redact_structure(value: Any) -> tuple[Any, dict[str, int]]:
    """Recursively convert arbitrary metadata to JSON-safe, redacted primitives."""

    detected: dict[str, int] = {}
    return _redact_json_value(value, detected, {}), detected


def redact_body(value: str, content_type: str | None = None) -> RedactionResult:
    """Redact structured request/response bodies without executing or interpreting code."""
    ctype = (content_type or "").split(";", 1)[0].strip().lower()
    stripped = value.lstrip()
    if ctype in {"application/json", "application/ld+json"} or stripped.startswith(("{", "[")):
        try:
            obj = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        else:
            detected: dict[str, int] = {}
            redacted = _redact_json_value(obj, detected, {})
            return RedactionResult(
                json.dumps(redacted, separators=(",", ":"), ensure_ascii=False), detected
            )
    if ctype == "application/x-www-form-urlencoded":
        form_detected: dict[str, int] = {}
        counters: dict[str, int] = {}
        items: list[tuple[str, str]] = []
        for key, raw in parse_qsl(value, keep_blank_values=True):
            normalized = key.strip().lower()
            if normalized in SENSITIVE_KEYS or any(
                marker in normalized for marker in ("token", "secret", "password", "passwd", "api_key")
            ):
                counters[normalized] = counters.get(normalized, 0) + 1
                form_detected[normalized] = form_detected.get(normalized, 0) + 1
                items.append((key, _token(normalized, counters[normalized])))
            else:
                items.append((key, raw))
        return RedactionResult(urlencode(items, doseq=True, safe="${}"), form_detected)
    return redact_text(value)
