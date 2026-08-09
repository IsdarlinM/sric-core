import base64
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import sric.updater as updater
from sric.updater import (
    ReleaseManifest,
    check_update,
    download_verified_artifact,
    load_and_verify_manifest,
    perform_update,
)


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


def _manifest(version: str) -> ReleaseManifest:
    return ReleaseManifest(
        product="sric-core",
        version=version,
        artifact="release.whl",
        sha256="0" * 64,
        signature="AA==",
    )


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


def test_same_version_is_noop_without_force(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest("0.5.3")
    monkeypatch.setattr(updater, "load_and_verify_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(
        updater,
        "install_verified_wheel",
        lambda *args, **kwargs: pytest.fail("same-version update installed without --force"),
    )

    status = perform_update(
        manifest_source="unused",
        public_key_path=Path("unused"),
        expected_product="sric-core",
        current_version="0.5.3",
        check_only=False,
        state_paths=[],
    )

    assert status.same_version is True
    assert status.update_available is False
    assert status.forced is False
    assert status.installed is False


def test_force_reinstalls_same_verified_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = _manifest("0.5.3")
    installs: list[tuple[Path, bool]] = []
    staged = tmp_path / "release.whl"
    staged.write_bytes(b"wheel")

    monkeypatch.setattr(updater, "load_and_verify_manifest", lambda *args, **kwargs: manifest)
    monkeypatch.setattr(updater, "download_verified_artifact", lambda *args, **kwargs: staged)
    monkeypatch.setattr(
        updater,
        "install_verified_wheel",
        lambda path, *, force_reinstall=False: installs.append((path, force_reinstall)),
    )
    monkeypatch.setattr(updater, "_verify_installed_distribution", lambda *args, **kwargs: None)

    status = perform_update(
        manifest_source="unused",
        public_key_path=Path("unused"),
        expected_product="sric-core",
        current_version="0.5.3",
        check_only=False,
        force=True,
        state_paths=[],
    )

    assert installs == [(staged, True)]
    assert status.same_version is True
    assert status.forced is True
    assert status.installed is True
    assert status.update_available is False


def test_force_never_downgrades(monkeypatch: pytest.MonkeyPatch) -> None:
    manifest = _manifest("0.5.2")
    monkeypatch.setattr(updater, "load_and_verify_manifest", lambda *args, **kwargs: manifest)

    with pytest.raises(ValueError, match="does not permit downgrades"):
        perform_update(
            manifest_source="unused",
            public_key_path=Path("unused"),
            expected_product="sric-core",
            current_version="0.5.3",
            check_only=False,
            force=True,
            state_paths=[],
        )


def test_check_and_force_are_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        perform_update(
            manifest_source="unused",
            public_key_path=Path("unused"),
            expected_product="sric-core",
            current_version="0.5.3",
            check_only=True,
            force=True,
            state_paths=[],
        )


def test_force_reinstall_adds_pip_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    wheel = tmp_path / "release.whl"
    wheel.write_bytes(b"wheel")

    def fake_run(command: list[str], **kwargs: object) -> None:
        calls.append(command)

    monkeypatch.setattr(updater.subprocess, "run", fake_run)
    updater.install_verified_wheel(wheel, force_reinstall=True)

    assert len(calls) == 1
    assert "--force-reinstall" in calls[0]
    assert calls[0][-1] == str(wheel)
