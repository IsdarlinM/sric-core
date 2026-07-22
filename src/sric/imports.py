from __future__ import annotations

import json
import mimetypes
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class ImportPolicy:
    max_file_bytes: int = 25 * 1024 * 1024
    max_archive_entries: int = 5000
    max_uncompressed_bytes: int = 250 * 1024 * 1024
    max_compression_ratio: float = 100.0


class SafeImportPipeline:
    """Central hostile-input gate for local imports. It never executes imported content."""

    def __init__(self, policy: ImportPolicy | None = None) -> None:
        self.policy = policy or ImportPolicy()

    def validate_file(self, path: Path) -> dict[str, Any]:
        if not path.is_file() or path.is_symlink():
            raise ValueError("import path must be a regular non-symlink file")
        size = path.stat().st_size
        if size > self.policy.max_file_bytes:
            raise ValueError("import file exceeds configured size limit")
        guessed, _ = mimetypes.guess_type(path.name)
        return {"size_bytes": size, "guessed_media_type": guessed or "application/octet-stream"}

    def load_json(self, path: Path) -> Any:
        self.validate_file(path)
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw)

    def inspect_zip(self, path: Path) -> dict[str, Any]:
        self.validate_file(path)
        total = 0
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > self.policy.max_archive_entries:
                raise ValueError("archive contains too many entries")
            for info in infos:
                member = PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ValueError("archive contains unsafe path traversal")
                unix_mode = info.external_attr >> 16
                if unix_mode and stat.S_ISLNK(unix_mode):
                    raise ValueError("archive symlinks are not allowed")
                total += info.file_size
                if total > self.policy.max_uncompressed_bytes:
                    raise ValueError("archive exceeds uncompressed size limit")
                if info.compress_size > 0 and info.file_size / info.compress_size > self.policy.max_compression_ratio:
                    raise ValueError("archive compression ratio exceeds safety limit")
        return {"entries": len(infos), "uncompressed_bytes": total}

    def safe_extract_zip(self, path: Path, destination: Path) -> list[Path]:
        self.inspect_zip(path)
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                member = PurePosixPath(info.filename)
                if info.is_dir():
                    continue
                out = destination.joinpath(*member.parts).resolve()
                if os.path.commonpath([str(destination), str(out)]) != str(destination):
                    raise ValueError("archive extraction escaped destination")
                out.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, open(out, "wb") as dst:
                    remaining = info.file_size
                    while remaining:
                        chunk = src.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        dst.write(chunk)
                        remaining -= len(chunk)
                written.append(out)
        return written
