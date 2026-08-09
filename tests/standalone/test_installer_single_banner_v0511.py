from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_linux_installer_suppresses_banner_for_internal_smokes() -> None:
    text = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    doctor = '"$VENV/bin/$CMD" doctor'
    assert doctor in text
    assert f"SENTINEL_BANNER=off {doctor}" not in text
    assert 'SENTINEL_BANNER=off "$VENV/bin/$CMD" capabilities' in text
    assert 'SENTINEL_BANNER=off "$VENV/bin/$CMD" --help' in text
    assert 'SENTINEL_BANNER=off "$VENV/bin/$CMD" -h' in text
    assert 'SENTINEL_BANNER=off "$VENV/bin/$CMD" help' in text


def test_windows_installer_enables_suppression_only_after_doctor() -> None:
    text = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    doctor_pos = text.index('"%VENV%\\Scripts\\%CMD%.exe" doctor')
    suppress_pos = text.index('set "SENTINEL_BANNER=off"')
    capabilities_pos = text.index('"%VENV%\\Scripts\\%CMD%.exe" capabilities')
    assert doctor_pos < suppress_pos < capabilities_pos
    assert 'set "SENTINEL_BANNER="' in text
