from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_windows_uninstaller_removes_runtime_but_preserves_data_and_shared_path() -> None:
    text = (ROOT / "scripts" / "uninstall-windows.cmd").read_text(encoding="utf-8")
    lowered = text.lower()
    assert "rmdir /s /q \"%venv%\"" in lowered
    assert "\\%cmd%.cmd" in lowered
    assert "rmdir /s /q \"%install_root%\"" not in lowered
    assert "sric.install_path" not in lowered
    assert "setx" not in lowered
    assert "preserved" in lowered
