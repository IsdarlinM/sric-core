from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_installers_do_not_force_reinstall_normal_runtime() -> None:
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    assert "--force-reinstall" not in linux
    assert "--force-reinstall" not in windows


def test_internal_cli_smokes_are_quiet_but_preserve_failure_logs() -> None:
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    for text in (linux, windows):
        assert "SENTINEL_BANNER=never" in text
        assert "install-check.log" in text
    assert 'cat "$CHECK_LOG"' in linux
    assert 'type "%CHECK_LOG%"' in windows


def test_installers_probe_web_catalog_runtime_module() -> None:
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    for text in (linux, windows):
        assert "sric.web_console" in text
        assert "sric.web_workbench" in text
        assert "sric.web_catalog" in text
        assert "pip check" in text
