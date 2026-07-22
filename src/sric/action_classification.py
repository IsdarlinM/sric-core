from __future__ import annotations

import re
from urllib.parse import urlsplit

from .models import ActionClass

_DESTRUCTIVE_PATH = re.compile(
    r"(?:^|/)(?:delete|destroy|purge|erase|wipe|terminate|revoke-all|rotate-key)(?:/|$)", re.I
)
_SENSITIVE_READ_PATH = re.compile(
    r"(?:^|/)(?:export|download|backup|admin|billing|audit|secrets?|tokens?|keys?)(?:/|$)", re.I
)
_MUTATING_GET_PATH = re.compile(
    r"(?:^|/)(?:logout|signout|unsubscribe|confirm|activate|deactivate|revoke|rotate)(?:/|$)", re.I
)


def classify_http_action(method: str, target: str) -> ActionClass:
    """Conservative deterministic baseline classification.

    This is not a vulnerability judgment. Callers may apply stricter workspace policy,
    but should not silently downgrade the returned class based on an AI suggestion.
    """
    method = method.upper().strip()
    path = urlsplit(target).path or "/"
    if method == "DELETE":
        return ActionClass.MUTATING_DESTRUCTIVE
    if method in {"POST", "PUT", "PATCH"}:
        if _DESTRUCTIVE_PATH.search(path):
            return ActionClass.MUTATING_DESTRUCTIVE
        return ActionClass.MUTATING_REVERSIBLE
    if method in {"GET", "HEAD", "OPTIONS"}:
        if _MUTATING_GET_PATH.search(path):
            return ActionClass.MUTATING_REVERSIBLE
        if _SENSITIVE_READ_PATH.search(path):
            return ActionClass.READ_ONLY_SENSITIVE
        return ActionClass.READ_ONLY_SAFE
    return ActionClass.READ_ONLY_SENSITIVE
