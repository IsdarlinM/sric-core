from __future__ import annotations

import os

from .redaction import redact_text

MAX_OPERATIONAL_ERROR_CHARS = 4096
_TRUE_VALUES = {"1", "true", "yes", "on"}


def debug_exceptions_enabled() -> bool:
    """Return whether raw unexpected exceptions may propagate for local debugging."""

    return os.getenv("SENTINEL_DEBUG", "").strip().lower() in _TRUE_VALUES


def safe_operational_text(value: object, *, max_chars: int = MAX_OPERATIONAL_ERROR_CHARS) -> str:
    """Return bounded, redacted text safe for user-visible output or persistence."""

    if max_chars < 64:
        raise ValueError("max_chars must be >= 64")
    raw = str(value).strip() or type(value).__name__
    safe = redact_text(raw).text.strip() or type(value).__name__
    if len(safe) <= max_chars:
        return safe
    return safe[: max_chars - 15] + "… [truncated]"


def safe_exception_message(exc: BaseException, *, max_chars: int = MAX_OPERATIONAL_ERROR_CHARS) -> str:
    """Return a bounded, redacted operational exception message safe for UI/CLI persistence."""

    return safe_operational_text(exc, max_chars=max_chars)
