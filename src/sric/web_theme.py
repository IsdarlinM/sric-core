from __future__ import annotations

"""Shared offline-safe visual tokens for Sentinel Forge Web surfaces.

The theme intentionally depends only on local/system fonts so dashboards, API references,
and the Security Workspace keep the same appearance in offline demos and restrictive CSPs.
"""

SENTINEL_FONT_STACK = (
    '"Segoe UI Variable Text", "Segoe UI Variable", Aptos, Inter, ui-sans-serif, '
    'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
)
SENTINEL_MONO_STACK = (
    '"Cascadia Code", SFMono-Regular, Consolas, "Liberation Mono", ui-monospace, monospace'
)

SENTINEL_THEME_TOKENS_CSS = rf"""
:root {{
  color-scheme: dark;
  font-family: {SENTINEL_FONT_STACK};
  background: #0b0f14;
  color: #e7edf3;
  --page: #0b0f14;
  --rail: #0e141b;
  --surface: #121922;
  --surface-2: #161f29;
  --surface-3: #0f151d;
  --line: #283544;
  --line-soft: #202b38;
  --text: #e7edf3;
  --text-soft: #b5c0ca;
  --muted: #8796a6;
  --accent: #5aa9b8;
  --accent-strong: #70bdca;
  --accent-soft: #132b31;
  --approval: #d2a15d;
  --approval-soft: #271f14;
  --danger: #d77b73;
  --success: #74b58c;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --font-sans: {SENTINEL_FONT_STACK};
  --font-mono: {SENTINEL_MONO_STACK};
}}
* {{ box-sizing: border-box; }}
html {{ background: var(--page); }}
body {{ margin: 0; min-height: 100vh; background: var(--page); color: var(--text); font-family: var(--font-sans); }}
a {{ color: inherit; }}
button, input, textarea, select {{ font: inherit; }}
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, a:focus-visible {{
  outline: 2px solid var(--accent-strong); outline-offset: 2px;
}}
""".strip()

SENTINEL_PANEL_CSS = r"""
.sentinel-panel {
  min-width: 0;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: 0 10px 28px rgba(0,0,0,.16);
}
""".strip()
