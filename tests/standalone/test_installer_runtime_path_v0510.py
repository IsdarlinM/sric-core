from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_linux_installer_prefers_existing_termux_prefix_bin() -> None:
    text = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    assert '${PREFIX}/bin' in text
    assert 'BIN_DIR="${PREFIX}/bin"' in text
    assert 'command -v python3' in text
    assert 'command -v python' in text
    assert 'Rebuilding obsolete or broken runtime environment' in text
    assert 'rm -rf "$VENV"' in text


def test_windows_installer_uses_sric_registry_helper_not_setx() -> None:
    text = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    assert '-m sric.install_path "%BIN_DIR%"' in text
    assert "setx PATH" not in text
    assert "reg add HKCU\\Environment" not in text
    assert 'rmdir /s /q "%VENV%"' in text
    assert "Rebuilding obsolete or broken runtime environment" in text


def test_runtime_recreation_preserves_data_roots() -> None:
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    assert 'rm -rf "$VENV"' in linux
    assert 'rm -rf "$INSTALL_ROOT"' not in linux
    assert 'rmdir /s /q "%VENV%"' in windows
    assert 'rmdir /s /q "%INSTALL_ROOT%"' not in windows
