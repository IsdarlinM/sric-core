from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from pydantic import BaseModel, ConfigDict, Field


class ReleaseManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product: str
    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$")
    artifact: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    signature: str

    def signed_payload(self) -> bytes:
        payload = self.model_dump(exclude={"signature"})
        return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


@dataclass(frozen=True)
class UpdateCheck:
    current_version: str
    available_version: str
    update_available: bool
    product: str
    artifact: str


def _semver_tuple(value: str) -> tuple[int, int, int]:
    core = value.split("-", 1)[0].split("+", 1)[0]
    major, minor, patch = core.split(".")
    return int(major), int(minor), int(patch)


def _read_source(source: str, *, max_bytes: int) -> bytes:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http"}:
        raise ValueError("insecure HTTP update sources are not allowed")
    if parsed.scheme == "https":
        with urllib.request.urlopen(source, timeout=15) as response:  # noqa: S310 - HTTPS enforced
            data = bytes(response.read(max_bytes + 1))
    elif parsed.scheme in {"", "file"}:
        path = Path(urllib.request.url2pathname(parsed.path) if parsed.scheme == "file" else source)
        if path.stat().st_size > max_bytes:
            raise ValueError("update source exceeds size limit")
        data = path.read_bytes()
    else:
        raise ValueError("update source must be a local path, file://, or https:// URL")
    if len(data) > max_bytes:
        raise ValueError("update source exceeds size limit")
    return data


def load_and_verify_manifest(
    source: str, public_key_path: Path, expected_product: str
) -> ReleaseManifest:
    manifest = ReleaseManifest.model_validate_json(_read_source(source, max_bytes=512 * 1024))
    if manifest.product != expected_product:
        raise ValueError(f"manifest product mismatch: expected {expected_product}")
    key = serialization.load_pem_public_key(public_key_path.read_bytes())
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("update trust root must be an Ed25519 public key")
    signature = base64.b64decode(manifest.signature, validate=True)
    key.verify(signature, manifest.signed_payload())
    return manifest


def check_update(manifest: ReleaseManifest, current_version: str) -> UpdateCheck:
    return UpdateCheck(
        current_version=current_version,
        available_version=manifest.version,
        update_available=_semver_tuple(manifest.version) > _semver_tuple(current_version),
        product=manifest.product,
        artifact=manifest.artifact,
    )


def download_verified_artifact(manifest: ReleaseManifest, destination: Path) -> Path:
    if not manifest.artifact.endswith(".whl"):
        raise ValueError("only signed wheel artifacts are accepted by the updater")
    data = _read_source(manifest.artifact, max_bytes=250 * 1024 * 1024)
    digest = hashlib.sha256(data).hexdigest()
    if digest != manifest.sha256:
        raise ValueError("release artifact SHA-256 mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, destination)
    return destination


def install_verified_wheel(path: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps", str(path)],
        check=True,
        shell=False,
    )


def perform_update(
    *,
    manifest_source: str,
    public_key_path: Path,
    expected_product: str,
    current_version: str,
    check_only: bool,
) -> UpdateCheck:
    manifest = load_and_verify_manifest(manifest_source, public_key_path, expected_product)
    status = check_update(manifest, current_version)
    if check_only or not status.update_available:
        return status
    with tempfile.TemporaryDirectory(prefix="sric-update-") as td:
        wheel = download_verified_artifact(
            manifest, Path(td) / Path(urllib.parse.urlparse(manifest.artifact).path).name
        )
        install_verified_wheel(wheel)
    return status
