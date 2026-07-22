from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .redaction import redact_text, redact_url


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def write(
        self,
        *,
        user: str,
        action: str,
        target: str,
        policy_decision: str,
        result: str,
        tool_version: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        safe_target = redact_text(redact_url(target).text).text
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": user,
            "action": action,
            "target": safe_target,
            "policy_decision": policy_decision,
            "result": result,
            "tool_version": tool_version,
            "metadata": metadata or {},
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True) + "\n")
