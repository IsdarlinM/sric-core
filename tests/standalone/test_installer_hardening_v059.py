from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_linux_installer_writes_a_valid_profile_path_line() -> None:
    text = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    assert "PATH_LINE='export PATH=\"$HOME/.local/bin:$PATH\"'" in text
    assert "PATH_LINE='export PATH=\\\"$HOME/.local/bin:$PATH\\\"'" not in text


def test_windows_installer_accepts_any_supported_python3() -> None:
    text = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    assert 'set "PY_CMD=py -3"' in text
    assert 'set "PY_CMD=py -3.11"' not in text
    assert "sys.version_info >= (3,11)" in text


def test_installers_verify_runtime_and_all_public_help_forms() -> None:
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    for text in (linux, windows):
        assert "pip check" in text
        assert "sric.web_console" in text
        assert "sric.web_workbench" in text
        assert "--help" in text
        assert " -h" in text or '" -h' in text
        assert " help" in text or '" help' in text
