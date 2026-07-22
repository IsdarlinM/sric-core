import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sric.updater import check_update, download_verified_artifact, load_and_verify_manifest


def _fixture(tmp_path: Path, *, tamper_signature: bool = False) -> tuple[Path, Path, bytes]:
    wheel = tmp_path / "sric_core-0.2.0-py3-none-any.whl"
    wheel_bytes = b"synthetic-wheel-fixture"
    wheel.write_bytes(wheel_bytes)
    private = Ed25519PrivateKey.generate()
    public = tmp_path / "release.pub.pem"
    public.write_bytes(
        private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    payload = {
        "product": "sric-core",
        "version": "0.2.0",
        "artifact": str(wheel),
        "sha256": hashlib.sha256(wheel_bytes).hexdigest(),
    }
    canonical = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    sig = private.sign(canonical)
    if tamper_signature:
        sig = b"x" * len(sig)
    payload["signature"] = base64.b64encode(sig).decode()
    manifest = tmp_path / "release.json"
    manifest.write_text(json.dumps(payload))
    return manifest, public, wheel_bytes


def test_signed_manifest_and_artifact_verification(tmp_path: Path) -> None:
    manifest_path, public, expected = _fixture(tmp_path)
    manifest = load_and_verify_manifest(str(manifest_path), public, "sric-core")
    assert check_update(manifest, "0.1.0").update_available
    out = download_verified_artifact(manifest, tmp_path / "staged.whl")
    assert out.read_bytes() == expected


def test_invalid_manifest_signature_fails_closed(tmp_path: Path) -> None:
    manifest_path, public, _ = _fixture(tmp_path, tamper_signature=True)
    with pytest.raises(Exception):
        load_and_verify_manifest(str(manifest_path), public, "sric-core")


def test_http_update_source_is_rejected(tmp_path: Path) -> None:
    _, public, _ = _fixture(tmp_path)
    with pytest.raises(ValueError, match="insecure HTTP"):
        load_and_verify_manifest("http://example.com/release.json", public, "sric-core")
