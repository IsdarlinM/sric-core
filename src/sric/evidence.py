from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

from .models import EvidenceReference, Provenance


class EvidenceStore:
    """Content-addressed evidence storage with explicit size limits and atomic writes."""

    def __init__(self, root: Path, max_bytes: int = 25 * 1024 * 1024) -> None:
        self.root = root
        self.max_bytes = max_bytes
        self.objects = root / "objects"
        self.metadata = root / "metadata"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.metadata.mkdir(parents=True, exist_ok=True)

    def put_bytes(
        self,
        data: bytes,
        *,
        media_type: str,
        provenance: Provenance,
        redacted: bool = False,
    ) -> EvidenceReference:
        if len(data) > self.max_bytes:
            raise ValueError(f"evidence exceeds configured limit of {self.max_bytes} bytes")
        digest = hashlib.sha256(data).hexdigest()
        evidence_id = f"EVD-{uuid4().hex[:12].upper()}"
        object_path = self.objects / digest[:2] / digest
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if not object_path.exists():
            tmp = object_path.with_suffix(".tmp")
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, object_path)
        ref = EvidenceReference(
            evidence_id=evidence_id,
            sha256=digest,
            media_type=media_type,
            size_bytes=len(data),
            provenance=provenance,
            redacted=redacted,
        )
        (self.metadata / f"{evidence_id}.json").write_text(
            json.dumps(ref.model_dump(mode="json"), indent=2), encoding="utf-8"
        )
        return ref

    def get_bytes(self, ref: EvidenceReference) -> bytes:
        path = self.objects / ref.sha256[:2] / ref.sha256
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != ref.sha256:
            raise ValueError("evidence integrity check failed")
        return data
