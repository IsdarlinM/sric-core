from __future__ import annotations

import html
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

from .web_console import WebConsoleConfig, WebConsoleManager
from .web_workbench import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    WORKBENCH_JS,
    WORKBENCH_SCHEMA_VERSION,
    build_feature_catalog,
    feature_contract,
)

SECURITY_WORKSPACE_UI_VERSION = 3


def _security_workspace_html(config: WebConsoleConfig, csrf_token: str) -> str:
    token = html.escape(csrf_token, quote=True)
    display_name = html.escape(config.display_name)
    version = html.escape(config.version)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="sentinel-workbench-token" content="{token}">
<title>{display_name} · Sentinel Forge Security Workspace</title>
<link rel="stylesheet" href="/workbench/styles.css">
</head>
<body>
<div class="forge-shell">
  <aside class="global-rail" aria-label="Sentinel Forge navigation">
    <div class="brand-lockup">
      <span class="brand-mark" aria-hidden="true">SF</span>
      <div>
        <p class="brand-name">Sentinel Forge</p>
        <p class="brand-caption">Evidence-native security research</p>
      </div>
    </div>

    <div class="product-lockup">
      <span class="rail-label">Active product</span>
      <strong>{display_name}</strong>
      <span class="product-version">v{version}</span>
    </div>

    <nav class="rail-nav" aria-label="Product navigation">
      <a class="rail-link" href="/">Dashboard</a>
      <span class="rail-link active" aria-current="page">Security Workspace</span>
      <a class="rail-link" href="/docs">API Reference</a>
    </nav>

    <div class="rail-principle" role="note">
      <span class="rail-label">Control principle</span>
      <strong>AI proposes.</strong>
      <span>Evidence proves.</span>
      <span>Humans control.</span>
    </div>
  </aside>

  <div class="workspace-shell">
    <header class="workspace-header">
      <div>
        <p class="eyebrow">Guided Security Operations</p>
        <h1>Security Workspace</h1>
        <p class="workspace-subtitle">Operate {display_name} through structured controls, evidence-aware output and explicit safety gates.</p>
      </div>
      <div class="workspace-status" aria-label="Interface status">
        <span class="status-label">Interface contract</span>
        <strong id="coverage">Loading…</strong>
        <span id="feature-count" class="status-count"></span>
      </div>
    </header>

    <section class="guardrail" aria-label="Execution guardrail">
      <div>
        <span class="guardrail-kicker">Execution guardrail</span>
        <strong>Scope, policy and human approval stay authoritative.</strong>
      </div>
      <p>No command syntax is required or accepted. Every operation is mapped from the installed CLI contract.</p>
    </section>

    <div class="mobile-tabs" aria-label="Console sections">
      <button type="button" data-mobile-target="catalog">Operations</button>
      <button type="button" data-mobile-target="runner">Configure</button>
      <button type="button" data-mobile-target="jobs">Activity</button>
    </div>

    <main class="workspace-grid">
      <aside class="panel catalog operations-library" id="catalog-panel">
        <div class="section-heading">
          <div>
            <span class="section-kicker">Operation library</span>
            <h2>Capabilities</h2>
          </div>
        </div>
        <label class="sr-only" for="feature-filter">Search operations</label>
        <div class="search-wrap">
          <span class="search-glyph" aria-hidden="true">⌕</span>
          <input id="feature-filter" type="search" placeholder="Search capabilities" autocomplete="off">
        </div>
        <div id="category-filters" class="chips" aria-label="Operation categories"></div>
        <div id="feature-list" class="feature-list" role="listbox" aria-label="Available operations"></div>
      </aside>

      <section class="panel runner operation-workspace" id="runner-panel">
        <div class="operation-header">
          <div class="operation-title-group">
            <span class="section-kicker">Operation workspace</span>
            <h2 id="feature-title">Select an operation</h2>
            <p id="feature-category" class="operation-category"></p>
          </div>
          <span id="classification" class="badge">—</span>
        </div>

        <p id="feature-help" class="operation-help muted"></p>

        <section class="configuration-card" aria-label="Operation configuration">
          <div class="configuration-heading">
            <div>
              <span class="section-kicker">Configuration</span>
              <strong>Parameters</strong>
            </div>
            <span class="configuration-note">Only enabled settings are serialized.</span>
          </div>
          <form id="feature-form" novalidate>
            <div id="fields" class="fields"></div>
          </form>
        </section>

        <div id="approval-box" class="approval hidden">
          <div class="approval-heading">
            <span class="approval-symbol" aria-hidden="true">!</span>
            <div>
              <p class="approval-title">Human approval required</p>
              <p>Review scope, destination and parameters before authorizing execution.</p>
            </div>
          </div>
          <label class="check">
            <input id="approved" type="checkbox">
            <span>I approve this operation after reviewing its scope and parameters.</span>
          </label>
          <label id="destructive-wrap" class="check destructive hidden">
            <input id="destructive-confirmed" type="checkbox">
            <span>I understand this operation is classified as destructive and may change or remove data.</span>
          </label>
        </div>

        <div class="execution-bar">
          <div class="actions">
            <button id="run" type="button" disabled>Run operation</button>
            <button id="cancel" type="button" class="secondary" disabled>Cancel</button>
          </div>
          <div id="job-meta" class="job-meta" aria-live="polite"></div>
        </div>

        <section class="output-card" aria-label="Operation evidence and output">
          <div class="output-head">
            <div>
              <span class="section-kicker">Execution evidence</span>
              <strong>Output</strong>
            </div>
            <span id="output-state" class="output-state"></span>
          </div>
          <pre id="output" aria-live="polite" tabindex="0">Select an operation to begin.</pre>
        </section>
      </section>

      <aside class="panel jobs activity-panel" id="jobs-panel">
        <div class="activity-header">
          <div>
            <span class="section-kicker">Execution history</span>
            <h2>Recent activity</h2>
          </div>
          <button id="refresh-jobs" type="button" class="ghost">Refresh</button>
        </div>
        <div id="jobs-list" class="jobs-list"></div>
      </aside>
    </main>
  </div>
</div>
<script src="/workbench/app.js" defer></script>
</body>
</html>"""


SECURITY_WORKSPACE_CSS = r"""
:root {
  color-scheme: dark;
  font-family: "Segoe UI Variable Text", "Segoe UI Variable", Aptos, Inter, ui-sans-serif,
    system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
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
}
* { box-sizing: border-box; }
html { background: var(--page); }
body { margin: 0; min-height: 100vh; background: var(--page); color: var(--text); }
a { color: inherit; }
button, input, textarea, select { font: inherit; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, a:focus-visible {
  outline: 2px solid var(--accent-strong); outline-offset: 2px;
}
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.forge-shell { min-height: 100vh; display: grid; grid-template-columns: 236px minmax(0, 1fr); }
.global-rail {
  position: sticky; top: 0; height: 100vh; display: flex; flex-direction: column; gap: 26px;
  padding: 24px 18px; background: var(--rail); border-right: 1px solid var(--line-soft);
}
.brand-lockup { display: flex; align-items: center; gap: 11px; }
.brand-mark {
  width: 38px; height: 38px; display: grid; place-items: center; border: 1px solid #36515b;
  border-radius: 10px; background: #102128; color: #91d1dc; font-weight: 800; letter-spacing: .04em;
}
.brand-name { margin: 0; font-size: .9rem; font-weight: 720; letter-spacing: .01em; }
.brand-caption { margin: 3px 0 0; color: var(--muted); font-size: .69rem; line-height: 1.35; }
.rail-label, .section-kicker, .status-label, .guardrail-kicker {
  display: block; color: var(--muted); font-size: .67rem; font-weight: 700; text-transform: uppercase; letter-spacing: .095em;
}
.product-lockup { display: grid; gap: 5px; padding: 14px; border: 1px solid var(--line-soft); border-radius: var(--radius-md); background: #111820; }
.product-lockup strong { font-size: 1rem; }
.product-version { width: fit-content; color: #a6b5c2; font-size: .74rem; }
.rail-nav { display: grid; gap: 6px; }
.rail-link { display: flex; align-items: center; min-height: 38px; padding: 0 11px; border-radius: var(--radius-sm); color: #9eadba; text-decoration: none; font-size: .82rem; }
a.rail-link:hover { background: #141f29; color: var(--text); }
.rail-link.active { background: #17252d; color: #d9eef1; box-shadow: inset 2px 0 0 var(--accent); }
.rail-principle { margin-top: auto; padding: 14px; border-top: 1px solid var(--line-soft); display: grid; gap: 4px; color: var(--text-soft); font-size: .78rem; }
.rail-principle strong { margin-top: 4px; color: #d8e4eb; }
.workspace-shell { width: min(1600px, 100%); margin: 0 auto; padding: 30px clamp(18px, 3vw, 42px) 42px; }
.workspace-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 30px; margin-bottom: 20px; }
.eyebrow { margin: 0 0 8px; color: #7fb5bf; font-size: .7rem; font-weight: 750; text-transform: uppercase; letter-spacing: .11em; }
.workspace-header h1 { margin: 0; font-size: clamp(1.8rem, 3vw, 2.7rem); line-height: 1.05; letter-spacing: -.025em; font-weight: 680; }
.workspace-subtitle { max-width: 760px; margin: 10px 0 0; color: var(--muted); line-height: 1.55; font-size: .9rem; }
.workspace-status { min-width: 210px; display: grid; gap: 5px; padding: 13px 15px; border: 1px solid var(--line); border-radius: var(--radius-md); background: var(--surface); }
.workspace-status strong { font-size: .8rem; color: #bcd3d8; }
.status-count { color: var(--muted); font-size: .72rem; }
.guardrail { display: flex; align-items: center; justify-content: space-between; gap: 26px; padding: 13px 16px; margin-bottom: 18px; border: 1px solid #29434b; border-radius: var(--radius-md); background: #101c22; }
.guardrail strong { display: block; margin-top: 4px; color: #dbe8eb; font-size: .84rem; }
.guardrail p { margin: 0; max-width: 700px; color: #91a5af; font-size: .78rem; line-height: 1.45; text-align: right; }
.workspace-grid { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: 16px; align-items: start; }
.panel { min-width: 0; background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius-lg); box-shadow: 0 10px 28px rgba(0,0,0,.16); }
.operations-library { position: sticky; top: 18px; padding: 16px; }
.section-heading, .operation-header, .configuration-heading, .output-head, .activity-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.section-heading h2, .activity-header h2 { margin: 5px 0 0; font-size: 1rem; font-weight: 650; }
.search-wrap { position: relative; margin-top: 15px; }
.search-glyph { position: absolute; left: 11px; top: 50%; transform: translateY(-50%); color: #667888; pointer-events: none; }
input, textarea, select { width: 100%; border: 1px solid #344252; border-radius: var(--radius-sm); background: #0d131a; color: var(--text); padding: 10px 11px; }
input::placeholder, textarea::placeholder { color: #5f6e7d; }
input[type=checkbox] { width: auto; accent-color: var(--accent); }
select[multiple] { min-height: 116px; }
#feature-filter { padding-left: 32px; }
.chips { display: flex; gap: 6px; overflow-x: auto; scrollbar-width: thin; padding: 11px 0 10px; }
.chip { white-space: nowrap; border: 1px solid #303d4c; background: #111820; color: #94a4b2; border-radius: 999px; padding: 6px 9px; font-size: .68rem; font-weight: 650; cursor: pointer; }
.chip.active { background: var(--accent-soft); border-color: #3e6f79; color: #b8e0e6; }
.feature-list { display: flex; flex-direction: column; gap: 5px; max-height: calc(100vh - 250px); overflow: auto; padding-right: 2px; }
.feature { appearance: none; width: 100%; border: 1px solid transparent; border-radius: 9px; background: transparent; color: #c6d0d9; text-align: left; padding: 10px 11px; cursor: pointer; }
.feature:hover { background: #151f28; border-color: #253341; }
.feature.active { background: #16252c; border-color: #345d66; box-shadow: inset 2px 0 0 var(--accent); }
.feature strong { display: block; font-size: .8rem; font-weight: 650; }
.feature small { display: block; color: #748595; margin-top: 4px; font-size: .68rem; line-height: 1.35; }
.operation-workspace { padding: 22px; }
.operation-header h2 { margin: 5px 0 4px; font-size: 1.45rem; font-weight: 650; letter-spacing: -.015em; }
.operation-category { margin: 0; color: #7d91a1; font-size: .76rem; }
.operation-help { margin: 12px 0 18px; max-width: 940px; }
.muted { color: var(--muted); line-height: 1.5; }
.badge { white-space: nowrap; border: 1px solid #3a4d5d; border-radius: 999px; padding: 6px 9px; color: #a9bac7; background: #111820; font-size: .66rem; font-weight: 700; letter-spacing: .02em; }
.configuration-card { border-top: 1px solid var(--line-soft); padding-top: 17px; }
.configuration-heading strong, .output-head strong { display: block; margin-top: 4px; font-size: .88rem; }
.configuration-note { color: #718292; font-size: .7rem; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 14px 0 4px; }
.field { border: 1px solid #293644; background: var(--surface-3); border-radius: var(--radius-md); padding: 12px; }
.field.full { grid-column: 1 / -1; }
.field-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 8px; }
.field-title { font-weight: 650; font-size: .79rem; }
.required { color: #ddb27a; font-size: .67rem; }
.field-help { color: #748493; font-size: .7rem; margin: 8px 0 0; line-height: 1.4; }
.use-option { display: flex; gap: 7px; align-items: center; color: #9cabb7; font-size: .71rem; margin-bottom: 8px; }
.boolean-card { display: flex; gap: 9px; align-items: flex-start; padding: 7px 0; color: #b9c5ce; font-size: .75rem; }
.boolean-card span { line-height: 1.4; }
.value-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; }
.approval { margin: 16px 0 0; padding: 14px; border: 1px solid #6d5534; background: var(--approval-soft); border-radius: var(--radius-md); }
.approval-heading { display: flex; gap: 10px; align-items: flex-start; margin-bottom: 9px; }
.approval-symbol { width: 24px; height: 24px; flex: 0 0 24px; display: grid; place-items: center; border-radius: 50%; background: #49361f; color: #efc98d; font-weight: 800; }
.approval-title { margin: 0; font-weight: 700; color: #e6c38d; }
.approval-heading p:last-child { margin: 4px 0 0; color: #a99578; font-size: .72rem; }
.check { display: flex; gap: 8px; align-items: flex-start; font-size: .77rem; margin: 7px 0; color: #c7b89f; }
.destructive { color: #e2a39d; }
.hidden { display: none !important; }
.execution-bar { display: flex; align-items: center; justify-content: space-between; gap: 14px; margin: 17px 0 12px; }
.actions { display: flex; gap: 8px; }
button { border: 1px solid transparent; border-radius: var(--radius-sm); padding: 9px 13px; background: var(--accent); color: #071216; font-weight: 700; cursor: pointer; }
button:hover:not(:disabled) { background: var(--accent-strong); }
button:disabled { opacity: .42; cursor: not-allowed; }
.secondary, .ghost { background: #151e27; color: #c6d0d9; border-color: #334150; }
.secondary:hover:not(:disabled), .ghost:hover:not(:disabled) { background: #1c2833; }
.ghost { padding: 7px 9px; font-size: .7rem; }
.job-meta { color: #8294a3; font-size: .72rem; text-align: right; }
.output-card { margin-top: 6px; border: 1px solid #26333f; border-radius: var(--radius-md); overflow: hidden; background: #090e13; }
.output-head { padding: 11px 13px; border-bottom: 1px solid #26333f; background: #10171f; }
.output-state { color: #8497a6; font-size: .7rem; }
pre { margin: 0; min-height: 220px; max-height: 44vh; overflow: auto; padding: 14px; color: #c7d7df; font: 12.5px/1.55 "Cascadia Code", "SFMono-Regular", Consolas, "Liberation Mono", monospace; white-space: pre-wrap; word-break: break-word; }
.activity-panel { grid-column: 1 / -1; padding: 16px; }
.activity-header { align-items: center; }
.jobs-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px; margin-top: 12px; max-height: 220px; overflow: auto; }
.job { border: 1px solid #2a3744; border-radius: 10px; padding: 10px 11px; background: #10171f; text-align: left; color: #ced8e0; }
.job:hover { border-color: #3b5666; background: #14202a; }
.job strong { display: block; font-size: .76rem; }
.job small { display: block; color: #778999; margin-top: 4px; font-size: .67rem; }
.mobile-tabs { display: none; }
@media (max-width: 1120px) {
  .forge-shell { grid-template-columns: 196px minmax(0, 1fr); }
  .workspace-grid { grid-template-columns: 260px minmax(0, 1fr); }
  .fields { grid-template-columns: 1fr; }
  .field.full { grid-column: auto; }
}
@media (max-width: 820px) {
  .forge-shell { display: block; }
  .global-rail { position: static; height: auto; padding: 12px 14px; display: grid; grid-template-columns: 1fr auto; align-items: center; border-right: 0; border-bottom: 1px solid var(--line-soft); }
  .brand-lockup { min-width: 0; }
  .brand-caption, .product-lockup, .rail-principle { display: none; }
  .rail-nav { display: flex; gap: 5px; justify-content: flex-end; }
  .rail-link { min-height: 32px; padding: 0 8px; font-size: .7rem; }
  .rail-link.active { display: none; }
  .workspace-shell { padding: 18px 12px 28px; }
  .workspace-header { align-items: flex-start; }
  .workspace-status { min-width: 170px; }
  .guardrail { align-items: flex-start; }
  .guardrail p { text-align: left; }
  .workspace-grid { grid-template-columns: 1fr; }
  .operations-library { position: static; }
  .activity-panel { grid-column: auto; }
}
@media (max-width: 760px) {
  .workspace-header { display: block; }
  .workspace-status { margin-top: 14px; }
  .guardrail { display: block; }
  .guardrail p { margin-top: 8px; }
  .mobile-tabs { display: flex; position: sticky; top: 0; z-index: 8; background: rgba(11,15,20,.96); gap: 6px; padding: 7px 0 10px; backdrop-filter: blur(10px); }
  .mobile-tabs button { flex: 1; background: #151e27; color: #cbd6de; border: 1px solid #334150; font-size: .72rem; }
  .panel { display: none; }
  .panel.mobile-active { display: block; }
  .catalog.mobile-active .feature-list { max-height: 56vh; }
  .fields { grid-template-columns: 1fr; }
  .execution-bar { align-items: flex-start; flex-direction: column; }
  .job-meta { text-align: left; }
  .jobs-list { display: flex; flex-direction: column; max-height: 56vh; }
  pre { min-height: 200px; max-height: 46vh; }
}
@media (max-width: 520px) {
  .global-rail { grid-template-columns: 1fr; gap: 9px; }
  .rail-nav { justify-content: flex-start; }
  .workspace-header h1 { font-size: 1.7rem; }
  .operation-workspace, .operations-library, .activity-panel { padding: 14px; }
  .operation-header { align-items: flex-start; }
  .badge { max-width: 46%; overflow: hidden; text-overflow: ellipsis; }
}
"""


def mount_security_workspace(
    app: FastAPI,
    config: WebConsoleConfig,
    manager: WebConsoleManager,
) -> None:
    """Mount the shared professional Sentinel Forge Security Workspace."""

    @app.get("/workbench", include_in_schema=False)
    async def security_workspace_page() -> HTMLResponse:
        return HTMLResponse(
            _security_workspace_html(config, manager.csrf_token),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/workbench/styles.css", include_in_schema=False)
    async def security_workspace_styles() -> PlainTextResponse:
        return PlainTextResponse(
            SECURITY_WORKSPACE_CSS,
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/workbench/app.js", include_in_schema=False)
    async def security_workspace_script() -> PlainTextResponse:
        return PlainTextResponse(
            WORKBENCH_JS,
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/workbench/catalog", tags=["web-workbench"])
    async def security_workspace_catalog() -> dict[str, Any]:
        features = build_feature_catalog(config.cli_module)
        categories = [
            {"key": key, "label": CATEGORY_LABELS[key]}
            for key in CATEGORY_ORDER
            if any(item["category"] == key for item in features)
        ]
        return {
            "schema_version": WORKBENCH_SCHEMA_VERSION,
            "ui_version": SECURITY_WORKSPACE_UI_VERSION,
            "product": config.product,
            "display_name": config.display_name,
            "version": config.version,
            "features": features,
            "categories": categories,
            "contract": feature_contract(config.cli_module),
            "execution": {
                "backend": "web-console-fixed-runner",
                "shell": False,
                "arbitrary_executable": False,
                "user_supplied_argv": False,
                "mutations_require_approval": True,
            },
        }

    @app.get("/api/v1/workbench/coverage", tags=["web-workbench"])
    async def security_workspace_coverage() -> dict[str, Any]:
        return feature_contract(config.cli_module)
