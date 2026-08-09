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
from dataclasses import dataclass, replace
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
    rollback_artifact: str | None = None
    rollback_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    def signed_payload(self) -> bytes:
        payload = self.model_dump(exclude={"signature"}, exclude_none=True)
        return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


@dataclass(frozen=True)
class UpdateCheck:
    current_version: str
    available_version: str
    update_available: bool
    product: str
    artifact: str
    same_version: bool = False
    forced: bool = False
    installed: bool = False


def _semver_parts(value: str) -> tuple[tuple[int, int, int], tuple[str, ...] | None]:
    precedence = value.split("+", 1)[0]
    core, separator, prerelease = precedence.partition("-")
    major, minor, patch = core.split(".")
    identifiers = tuple(prerelease.split(".")) if separator else None
    return (int(major), int(minor), int(patch)), identifiers


def _compare_semver(left: str, right: str) -> int:
    left_core, left_pre = _semver_parts(left)
    right_core, right_pre = _semver_parts(right)
    if left_core != right_core:
        return 1 if left_core > right_core else -1
    if left_pre is None and right_pre is None:
        return 0
    if left_pre is None:
        return 1
    if right_pre is None:
        return -1
    for left_id, right_id in zip(left_pre, right_pre):
        if left_id == right_id:
            continue
        left_numeric = left_id.isdigit()
        right_numeric = right_id.isdigit()
        if left_numeric and right_numeric:
            return 1 if int(left_id) > int(right_id) else -1
        if left_numeric != right_numeric:
            return -1 if left_numeric else 1
        return 1 if left_id > right_id else -1
    if len(left_pre) == len(right_pre):
        return 0
    return 1 if len(left_pre) > len(right_pre) else -1


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
    comparison = _compare_semver(manifest.version, current_version)
    return UpdateCheck(
        current_version=current_version,
        available_version=manifest.version,
        update_available=comparison > 0,
        same_version=comparison == 0,
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


def install_verified_wheel(path: Path, *, force_reinstall: bool = False) -> None:
    command = [sys.executable, "-m", "pip", "install", "--upgrade", "--no-deps"]
    if force_reinstall:
        command.append("--force-reinstall")
    command.append(str(path))
    subprocess.run(command, check=True, shell=False)


def _download_hashed_wheel(source: str, expected_sha256: str, destination: Path) -> Path:
    if not source.endswith(".whl"):
        raise ValueError("rollback artifacts must be wheel files")
    data = _read_source(source, max_bytes=250 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise ValueError("rollback artifact SHA-256 mismatch")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return destination


def _default_state_paths(product: str) -> list[Path]:
    mapping = {
        "sric-core": [Path.home() / ".sric"],
        "reprosec": [Path.home() / ".reprosec"],
        "authtwin": [Path.home() / ".authtwin"],
        "fossilscope": [Path.home() / ".fossilscope"],
        "trustboundary": [Path.home() / ".trustboundary"],
        "exposuredna": [Path.home() / ".exposuredna"],
    }
    return mapping.get(product, [])


def _backup_state(paths: list[Path], destination: Path) -> list[tuple[Path, Path]]:
    import shutil

    backups = []
    destination.mkdir(parents=True, exist_ok=True)
    for idx, source in enumerate(paths):
        if not source.exists() or source.is_symlink():
            continue
        target = destination / f"state-{idx}"
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                symlinks=False,
                ignore=shutil.ignore_patterns("*.tmp", ".workspace.lock"),
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target, follow_symlinks=False)
        backups.append((source, target))
    return backups


def _restore_state(backups: list[tuple[Path, Path]]) -> None:
    import shutil

    for target, backup in backups:
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        if backup.is_dir():
            shutil.copytree(backup, target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)


def _verify_installed_distribution(product: str, expected_version: str) -> None:
    import importlib.metadata

    observed = importlib.metadata.version(product)
    if observed != expected_version:
        raise RuntimeError(
            f"installed version verification failed: expected {expected_version}, observed {observed}"
        )


def perform_update(
    *,
    manifest_source: str,
    public_key_path: Path,
    expected_product: str,
    current_version: str,
    check_only: bool,
    force: bool = False,
    state_paths: list[Path] | None = None,
    require_rollback: bool = True,
) -> UpdateCheck:
    if check_only and force:
        raise ValueError("--check and --force are mutually exclusive")

    manifest = load_and_verify_manifest(manifest_source, public_key_path, expected_product)
    status = check_update(manifest, current_version)
    comparison = _compare_semver(manifest.version, current_version)

    if force and comparison < 0:
        raise ValueError(
            "forced update does not permit downgrades; use the explicit rollback/recovery workflow"
        )
    if check_only:
        return status
    if not status.update_available and not force:
        return status

    same_version_reinstall = force and status.same_version
    if (
        require_rollback
        and not same_version_reinstall
        and (not manifest.rollback_artifact or not manifest.rollback_sha256)
    ):
        raise ValueError(
            "installing an update requires a verified rollback_artifact and rollback_sha256"
        )

    with tempfile.TemporaryDirectory(prefix="sric-update-") as td:
        transaction = Path(td)
        wheel = download_verified_artifact(
            manifest,
            transaction / Path(urllib.parse.urlparse(manifest.artifact).path).name,
        )
        rollback: Path | None = wheel if same_version_reinstall else None
        if not same_version_reinstall and manifest.rollback_artifact and manifest.rollback_sha256:
            rollback = _download_hashed_wheel(
                manifest.rollback_artifact,
                manifest.rollback_sha256,
                transaction
                / ("rollback-" + Path(urllib.parse.urlparse(manifest.rollback_artifact).path).name),
            )
        backups = _backup_state(
            state_paths if state_paths is not None else _default_state_paths(expected_product),
            transaction / "state-backup",
        )
        try:
            install_verified_wheel(wheel, force_reinstall=force)
            _verify_installed_distribution(expected_product, manifest.version)
        except Exception as exc:
            rollback_error = None
            if rollback is not None:
                try:
                    install_verified_wheel(rollback, force_reinstall=True)
                    expected_rollback_version = (
                        manifest.version if same_version_reinstall else current_version
                    )
                    _verify_installed_distribution(expected_product, expected_rollback_version)
                except Exception as rb_exc:
                    rollback_error = rb_exc
            _restore_state(backups)
            if rollback_error:
                raise RuntimeError(
                    "update failed and rollback also failed: "
                    f"update={exc}; rollback={rollback_error}"
                ) from exc
            raise RuntimeError(f"update failed; previous package/state restored: {exc}") from exc

    return replace(status, forced=force, installed=True)
