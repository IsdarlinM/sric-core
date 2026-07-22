from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .db import Database


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def create(cls, root: Path, name: str) -> "Workspace":
        if not name or any(c in name for c in "/\\\0"):
            raise ValueError("workspace name contains unsafe characters")
        path = root / name
        path.mkdir(parents=True, exist_ok=False)
        for sub in ("evidence", "plugins", "reports", "backups"):
            (path / sub).mkdir()
        metadata = {"name": name, "schema_version": "1", "telemetry": False, "cloud_ai": False}
        (path / "workspace.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        db = Database(path / "workspace.db")
        db.bootstrap()
        return cls(path)

    @classmethod
    def open(cls, path: Path) -> "Workspace":
        if not (path / "workspace.json").is_file():
            raise FileNotFoundError("workspace.json not found")
        return cls(path)
