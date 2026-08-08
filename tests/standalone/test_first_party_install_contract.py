from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_sric_has_no_mandatory_sibling_dependencies() -> None:
    text = (ROOT / "requirements" / "first-party.txt").read_text(encoding="utf-8")
    for sibling in ("reprosec", "authtwin", "fossilscope", "trustboundary", "exposuredna"):
        assert sibling not in text.lower()


def test_installers_consume_first_party_manifest() -> None:
    windows = (ROOT / "scripts" / "install-windows.cmd").read_text(encoding="utf-8")
    linux = (ROOT / "scripts" / "install-linux.sh").read_text(encoding="utf-8")
    assert '-r "%FIRST_PARTY%"' in windows
    assert '-r "$FIRST_PARTY"' in linux
