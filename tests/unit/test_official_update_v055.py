from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from sric import updater
from sric.updater import OfficialReleaseChannel, UpdateCheck


def _channel(version: str = "0.5.5") -> OfficialReleaseChannel:
    return OfficialReleaseChannel(
        product="sric-core",
        repository="IsdarlinM/sric-core",
        version=version,
        commit="a" * 40,
        rollback_version="0.5.4",
        rollback_commit="b" * 40,
    )


def test_product_update_uses_official_channel_without_manifest_or_key(monkeypatch) -> None:
    expected = UpdateCheck(
        current_version="0.5.5",
        available_version="0.5.5",
        update_available=False,
        same_version=True,
        product="sric-core",
        artifact="official",
        channel="official-github-signed-commit",
    )
    seen: dict[str, object] = {}

    def fake_official(**kwargs):
        seen.update(kwargs)
        return expected

    monkeypatch.setattr(updater, "perform_official_update", fake_official)
    result = updater.perform_product_update(
        expected_product="sric-core",
        current_version="0.5.5",
        check_only=False,
        force=True,
    )
    assert result is expected
    assert seen["force"] is True
    assert seen["expected_product"] == "sric-core"


def test_custom_channel_requires_manifest_and_key_together(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="both manifest source and public key"):
        updater.perform_product_update(
            expected_product="sric-core",
            current_version="0.5.5",
            check_only=False,
            force=True,
            manifest_source="release.json",
            public_key_path=None,
        )


def test_official_force_reinstalls_same_version(monkeypatch, tmp_path: Path) -> None:
    channel = _channel("0.5.5")
    target = tmp_path / "target.zip"
    target.write_bytes(b"zip")
    installs: list[tuple[Path, bool]] = []

    monkeypatch.setattr(updater, "_load_official_channel", lambda product: channel)
    monkeypatch.setattr(updater, "_download_official_archive", lambda **kwargs: target)
    monkeypatch.setattr(updater, "_backup_state", lambda paths, destination: [])
    monkeypatch.setattr(updater, "_verify_installed_distribution", lambda product, version: None)
    monkeypatch.setattr(
        updater,
        "install_verified_package",
        lambda path, force_reinstall=False: installs.append((path, force_reinstall)),
    )

    result = updater.perform_official_update(
        expected_product="sric-core",
        current_version="0.5.5",
        check_only=False,
        force=True,
        state_paths=[],
    )
    assert result.installed is True
    assert result.forced is True
    assert result.same_version is True
    assert installs == [(target, True)]


def test_official_force_refuses_downgrade(monkeypatch) -> None:
    monkeypatch.setattr(updater, "_load_official_channel", lambda product: _channel("0.5.4"))
    with pytest.raises(ValueError, match="does not permit downgrades"):
        updater.perform_official_update(
            expected_product="sric-core",
            current_version="0.5.5",
            check_only=False,
            force=True,
        )


def test_unverified_github_commit_is_rejected(monkeypatch) -> None:
    payload = b'{"sha":"' + (b"a" * 40) + b'","commit":{"verification":{"verified":false,"reason":"unsigned"}}}'
    monkeypatch.setattr(updater, "_read_source", lambda source, max_bytes: payload)
    with pytest.raises(ValueError, match="not GitHub signature-verified"):
        updater._verify_github_commit("IsdarlinM/sric-core", "a" * 40)


def test_source_archive_rejects_traversal() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("repo-aaaaaaa/pyproject.toml", '[project]\nname="sric-core"\nversion="0.5.5"\n')
        archive.writestr("repo-aaaaaaa/../escape.txt", "no")
    with pytest.raises(ValueError, match="unsafe path"):
        updater._validate_source_archive(
            buffer.getvalue(),
            expected_product="sric-core",
            expected_version="0.5.5",
            expected_commit="a" * 40,
        )


def test_source_archive_rejects_symlink() -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("repo-aaaaaaa/pyproject.toml", '[project]\nname="sric-core"\nversion="0.5.5"\n')
        info = zipfile.ZipInfo("repo-aaaaaaa/link")
        info.create_system = 3
        info.external_attr = (0o120777 << 16)
        archive.writestr(info, "target")
    with pytest.raises(ValueError, match="symlink"):
        updater._validate_source_archive(
            buffer.getvalue(),
            expected_product="sric-core",
            expected_version="0.5.5",
            expected_commit="a" * 40,
        )
