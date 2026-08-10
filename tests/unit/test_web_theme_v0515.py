from sric.web_theme import SENTINEL_MONO_STACK, SENTINEL_THEME_TOKENS_CSS


def test_shared_theme_matches_security_workspace_visual_contract() -> None:
    css = SENTINEL_THEME_TOKENS_CSS
    assert "#0b0f14" in css
    assert "#121922" in css
    assert "#283544" in css
    assert "#5aa9b8" in css
    assert "Segoe UI Variable Text" in css
    assert "Aptos" in css
    assert "--font-mono" in css
    assert "Cascadia Code" in SENTINEL_MONO_STACK
    assert "http://" not in css
    assert "https://" not in css
