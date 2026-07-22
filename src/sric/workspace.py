from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from .db import Database

WORKSPACE_SCHEMA_VERSION = "2"
PRODUCT_NAMESPACES = ("reprosec", "authtwin", "fossilscope", "trustboundary", "exposuredna")
SHARED_DIRS = ("evidence", "graph", "lineage", "jobs", "notebooks", "secrets", "plugins", "reports", "backups")


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_name(name: str) -> str:
    if not name or any(c in name for c in "/\\\0") or name in {".", ".."}:
        raise ValueError("workspace name contains unsafe characters")
    return name


@dataclass(frozen=True)
class Workspace:
    root: Path

    @classmethod
    def create(cls, root: Path, name: str) -> "Workspace":
        _safe_name(name)
        path = root / name
        path.mkdir(parents=True, exist_ok=False)
        for sub in (*SHARED_DIRS, *PRODUCT_NAMESPACES):
            (path / sub).mkdir()
        metadata = {
            "workspace_id": f"WS-{uuid4().hex.upper()}",
            "name": name,
            "schema_version": WORKSPACE_SCHEMA_VERSION,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "telemetry": False,
            "cloud_ai": False,
            "external_uploads": False,
            "products": {product: {"schema_version": "1"} for product in PRODUCT_NAMESPACES},
        }
        (path / "workspace.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        db = Database(path / "workspace.db")
        db.bootstrap()
        return cls(path)

    @classmethod
    def open(cls, path: Path, *, migrate: bool = True) -> "Workspace":
        path = path.resolve()
        if not (path / "workspace.json").is_file():
            raise FileNotFoundError("workspace.json not found")
        ws = cls(path)
        if migrate:
            ws.migrate()
        return ws

    @property
    def metadata(self) -> dict[str, object]:
        raw = json.loads((self.root / "workspace.json").read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("workspace metadata must be an object")
        return raw

    def namespace(self, product: str) -> Path:
        if product not in PRODUCT_NAMESPACES:
            raise ValueError(f"unknown product namespace: {product}")
        path = self.root / product
        path.mkdir(exist_ok=True)
        return path

    @contextmanager
    def lock(self, *, timeout_seconds: float = 10.0) -> Iterator[None]:
        lock_path = self.root / ".workspace.lock"
        start = time.monotonic()
        fd: int | None = None
        while fd is None:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                os.write(fd, f"pid={os.getpid()}\ncreated={_utcnow()}\n".encode())
            except FileExistsError:
                if time.monotonic() - start >= timeout_seconds:
                    raise TimeoutError("workspace lock acquisition timed out")
                time.sleep(0.05)
        try:
            yield
        finally:
            os.close(fd)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    def migrate(self) -> list[str]:
        changes: list[str] = []
        meta = self.metadata
        version = str(meta.get("schema_version", "1"))
        if version not in {"1", WORKSPACE_SCHEMA_VERSION}:
            raise ValueError(f"unsupported workspace schema_version: {version}")
        if version == "1":
            for sub in (*SHARED_DIRS, *PRODUCT_NAMESPACES):
                (self.root / sub).mkdir(exist_ok=True)
            meta.setdefault("workspace_id", f"WS-{uuid4().hex.upper()}")
            meta.setdefault("external_uploads", False)
            meta.setdefault("products", {product: {"schema_version": "1"} for product in PRODUCT_NAMESPACES})
            meta["schema_version"] = WORKSPACE_SCHEMA_VERSION
            meta["updated_at"] = _utcnow()
            (self.root / "workspace.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            changes.append("1->2")
        else:
            for sub in (*SHARED_DIRS, *PRODUCT_NAMESPACES):
                (self.root / sub).mkdir(exist_ok=True)
        return changes

    def backup(self, destination: Path | None = None) -> Path:
        destination = destination or (self.root / "backups" / f"workspace-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
        if destination.resolve().is_relative_to(self.root.resolve()) and "backups" not in destination.parts:
            raise ValueError("backup destination inside workspace must be under backups/")
        destination.parent.mkdir(parents=True, exist_ok=True)
        ignore = shutil.ignore_patterns("backups", ".workspace.lock", "*.tmp")
        shutil.copytree(self.root, destination, ignore=ignore)
        return destination

    @classmethod
    def restore(cls, backup: Path, destination: Path) -> "Workspace":
        if destination.exists():
            raise FileExistsError(destination)
        if not (backup / "workspace.json").is_file():
            raise ValueError("backup does not contain workspace.json")
        shutil.copytree(backup, destination)
        return cls.open(destination)

    def integrity(self) -> dict[str, object]:
        required = ["workspace.json", "workspace.db", *SHARED_DIRS, *PRODUCT_NAMESPACES]
        missing = [item for item in required if not (self.root / item).exists()]
        hashes: dict[str, str] = {}
        for name in ("workspace.json", "workspace.db"):
            path = self.root / name
            if path.is_file():
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        meta = self.metadata
        return {
            "ok": not missing and str(meta.get("schema_version")) == WORKSPACE_SCHEMA_VERSION,
            "workspace_id": meta.get("workspace_id"),
            "schema_version": meta.get("schema_version"),
            "missing": missing,
            "hashes": hashes,
            "privacy_defaults": {
                "telemetry": meta.get("telemetry", False),
                "cloud_ai": meta.get("cloud_ai", False),
                "external_uploads": meta.get("external_uploads", False),
            },
        }
