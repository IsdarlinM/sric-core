from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

from .web_console import WebConsoleConfig, WebConsoleManager, build_command_catalog

WORKBENCH_SCHEMA_VERSION = 2
SENSITIVE_MARKERS = (
    "token",
    "secret",
    "password",
    "passwd",
    "pwd",
    "cookie",
    "authorization",
    "api-key",
    "api_key",
    "apikey",
    "private-key",
    "private_key",
)
CATEGORY_LABELS = {
    "workspace": "Workspace & configuration",
    "acquire": "Observe, capture & import",
    "analyze": "Analysis & research",
    "evidence": "Evidence, reports & export",
    "safety": "Scope, policy & approvals",
    "integrations": "AI & plugins",
    "system": "System & maintenance",
    "other": "Other capabilities",
}
CATEGORY_ORDER = tuple(CATEGORY_LABELS)


def _category(path: str) -> str:
    root = path.split(" ", 1)[0].lower().replace("_", "-")
    if root in {"init", "workspace", "config", "set"}:
        return "workspace"
    if root in {"observe", "capture", "import", "collect", "collect-url", "record", "add"}:
        return "acquire"
    if root in {
        "analyze",
        "analysis",
        "graph",
        "timeline",
        "search",
        "query",
        "inspect",
        "diff",
        "matrix",
        "findings",
        "coverage",
        "fossils",
        "lifecycle",
        "history",
        "explain",
        "assumptions",
        "lineage",
        "notebook",
        "reobserve",
        "reobservation",
        "evolution",
        "correlate",
    }:
        return "analyze"
    if root in {"report", "export", "pack", "verify", "sign", "redact", "compile"}:
        return "evidence"
    if root in {"scope", "policy", "approve", "approval", "replay", "validate"}:
        return "safety"
    if root in {"ai", "plugins", "plugin"}:
        return "integrations"
    if root in {"doctor", "update", "version", "capabilities", "status", "help"}:
        return "system"
    return "other"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "operation"


def _title(value: str) -> str:
    return " ".join(part.replace("-", " ").title() for part in value.split())


def _is_sensitive(name: str) -> bool:
    normalized = name.lower().replace("_", "-")
    return any(marker.replace("_", "-") in normalized for marker in SENSITIVE_MARKERS)


def _control_for(param: dict[str, Any]) -> str:
    choices = list(param.get("choices") or [])
    if param.get("kind") == "option" and param.get("is_flag"):
        return "tri-state" if param.get("secondary_opts") else "flag"
    if param.get("count"):
        return "count"
    if choices:
        return "multi-select" if param.get("multiple") else "select"
    nargs = int(param.get("nargs", 1))
    if nargs > 1:
        return "multi-value"
    if param.get("multiple") or nargs < 0:
        return "multi-text"
    type_name = str(param.get("type") or "").lower()
    if "path" in type_name or param.get("path"):
        return "path"
    if any(token in type_name for token in ("int", "float", "number", "range")):
        return "number"
    if "bool" in type_name:
        return "flag"
    return "text"


def _web_param(param: dict[str, Any], index: int) -> dict[str, Any]:
    opts = [str(item) for item in param.get("opts", [])]
    secondary_opts = [str(item) for item in param.get("secondary_opts", [])]
    name = str(param.get("name") or f"param-{index}")
    return {
        "id": f"p{index}-{_slug(name)}",
        "name": name,
        "label": name.replace("_", " ").replace("-", " ").title(),
        "kind": str(param.get("kind") or "argument"),
        "required": bool(param.get("required")),
        "multiple": bool(param.get("multiple")),
        "nargs": int(param.get("nargs", 1)),
        "default": param.get("default"),
        "type": str(param.get("type") or "text"),
        "help": str(param.get("help") or ""),
        "is_flag": bool(param.get("is_flag")),
        "count": bool(param.get("count")),
        "opts": opts,
        "secondary_opts": secondary_opts,
        "primary_opt": opts[0] if opts else None,
        "negative_opt": secondary_opts[0] if secondary_opts else None,
        "choices": list(param.get("choices") or []),
        "min": param.get("min"),
        "max": param.get("max"),
        "path": param.get("path"),
        "control": _control_for(param),
        "sensitive": _is_sensitive(name) or any(_is_sensitive(opt) for opt in opts),
    }


def build_feature_catalog(cli_module: str) -> list[dict[str, Any]]:
    """Create the guided Web operation schema from the real installed CLI tree."""
    features: list[dict[str, Any]] = []
    for command in build_command_catalog(cli_module):
        path = str(command["path"])
        category = _category(path)
        features.append(
            {
                "id": _slug(path),
                "path": path,
                "title": _title(path),
                "help": str(command.get("help") or ""),
                "category": category,
                "category_label": CATEGORY_LABELS[category],
                "classification": str(command.get("classification") or "UNKNOWN"),
                "approval_required": bool(command.get("approval_required")),
                "approval_phrase_required": bool(command.get("approval_phrase_required")),
                "context_only": bool(command.get("context_only")),
                "executable": bool(command.get("executable")),
                "is_group": bool(command.get("is_group")),
                "params": [
                    _web_param(param, i) for i, param in enumerate(command.get("params", []))
                ],
                "web_surface": "context" if command.get("context_only") else "structured-form",
            }
        )
    return features


def feature_contract(cli_module: str) -> dict[str, Any]:
    cli = build_command_catalog(cli_module)
    web = build_feature_catalog(cli_module)
    cli_by_path = {str(item["path"]): item for item in cli}
    web_by_path = {str(item["path"]): item for item in web}
    missing = sorted(set(cli_by_path) - set(web_by_path))
    extra = sorted(set(web_by_path) - set(cli_by_path))
    mismatches: list[dict[str, Any]] = []
    for path in sorted(set(cli_by_path) & set(web_by_path)):
        cli_params = [str(item.get("name")) for item in cli_by_path[path].get("params", [])]
        web_params = [str(item.get("name")) for item in web_by_path[path].get("params", [])]
        if cli_params != web_params:
            mismatches.append({"path": path, "cli": cli_params, "web": web_params})
    payload = {
        "schema_version": WORKBENCH_SCHEMA_VERSION,
        "cli_commands": len(cli),
        "web_features": len(web),
        "missing_commands": missing,
        "extra_features": extra,
        "parameter_mismatches": mismatches,
        "complete": not missing and not extra and not mismatches,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["fingerprint"] = hashlib.sha256(canonical).hexdigest()
    return payload


def assert_feature_contract(cli_module: str) -> dict[str, Any]:
    contract = feature_contract(cli_module)
    if not contract["complete"]:
        raise AssertionError(f"CLI/Web feature contract incomplete: {contract}")
    return contract


def _workbench_html(config: WebConsoleConfig, csrf_token: str) -> str:
    token = html.escape(csrf_token, quote=True)
    display_name = html.escape(config.display_name)
    version = html.escape(config.version)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="sentinel-workbench-token" content="{token}">
<title>{display_name} Security Console</title>
<link rel="stylesheet" href="/workbench/styles.css">
</head>
<body>
<div class="app-shell">
  <header class="topbar">
    <div>
      <p class="eyebrow">Sentinel Forge · guided security operations</p>
      <h1>{display_name}</h1>
      <p class="subtitle">Security Console</p>
    </div>
    <div class="top-actions">
      <span class="version">v{version}</span>
      <a href="/" class="nav-link">Dashboard</a>
      <a href="/docs" class="nav-link">API</a>
    </div>
  </header>

  <section class="principle" role="note">
    <strong>AI proposes. Evidence proves. Humans control.</strong>
    <span>Choose an operation, configure it with guided controls, review safety requirements, and run it. No command syntax is required.</span>
  </section>

  <div class="mobile-tabs" aria-label="Console sections">
    <button type="button" data-mobile-target="catalog">Operations</button>
    <button type="button" data-mobile-target="runner">Configure</button>
    <button type="button" data-mobile-target="jobs">Activity</button>
  </div>

  <main class="layout">
    <aside class="panel catalog" id="catalog-panel">
      <div class="panel-head">
        <div><span class="label">Operations</span><strong id="coverage">Loading…</strong></div>
        <span id="feature-count" class="muted"></span>
      </div>
      <label class="sr-only" for="feature-filter">Search operations</label>
      <input id="feature-filter" type="search" placeholder="Search operations" autocomplete="off">
      <div id="category-filters" class="chips" aria-label="Operation categories"></div>
      <div id="feature-list" class="feature-list" role="listbox" aria-label="Available operations"></div>
    </aside>

    <section class="panel runner" id="runner-panel">
      <div class="feature-heading">
        <div>
          <span class="label">Selected operation</span>
          <h2 id="feature-title">Select an operation</h2>
          <p id="feature-category" class="operation-category"></p>
        </div>
        <span id="classification" class="badge">—</span>
      </div>
      <p id="feature-help" class="muted"></p>
      <form id="feature-form" novalidate>
        <div id="fields" class="fields"></div>
      </form>

      <div id="approval-box" class="approval hidden">
        <p class="approval-title">Human approval required</p>
        <label class="check">
          <input id="approved" type="checkbox">
          <span>I approve this operation after reviewing its scope and parameters.</span>
        </label>
        <label id="destructive-wrap" class="check destructive hidden">
          <input id="destructive-confirmed" type="checkbox">
          <span>I understand this operation is classified as destructive and may change or remove data.</span>
        </label>
      </div>

      <div class="actions">
        <button id="run" type="button" disabled>Run operation</button>
        <button id="cancel" type="button" class="secondary" disabled>Cancel</button>
      </div>
      <div id="job-meta" class="job-meta" aria-live="polite"></div>
      <section class="output-card" aria-label="Operation output">
        <div class="output-head"><span>Evidence & output</span><span id="output-state"></span></div>
        <pre id="output" aria-live="polite" tabindex="0">Select an operation to begin.</pre>
      </section>
    </section>

    <aside class="panel jobs" id="jobs-panel">
      <div class="panel-head">
        <span class="label">Recent activity</span>
        <button id="refresh-jobs" type="button" class="ghost">Refresh</button>
      </div>
      <div id="jobs-list" class="jobs-list"></div>
    </aside>
  </main>
</div>
<script src="/workbench/app.js" defer></script>
</body>
</html>"""


WORKBENCH_CSS = r"""
:root {
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color-scheme: dark;
  background: #090d0b;
  color: #e8f0eb;
  --panel: #101612;
  --panel-soft: #0c120e;
  --line: #26352c;
  --muted: #8fa397;
  --accent: #78c38d;
  --accent-soft: #173021;
  --danger: #e3a27b;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: radial-gradient(circle at top right, #163323 0, #090d0b 34rem); }
a { color: inherit; }
button, input, textarea, select { font: inherit; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, a:focus-visible {
  outline: 2px solid var(--accent); outline-offset: 2px;
}
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0,0,0,0); white-space: nowrap; border: 0; }
.app-shell { width: min(1500px, calc(100% - 24px)); margin: 0 auto; padding: 20px 0 36px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 18px; margin-bottom: 12px; }
.topbar h1 { margin: .1rem 0 0; font-size: clamp(1.55rem, 3vw, 2.25rem); }
.subtitle { margin: .2rem 0 0; color: #b7cabc; }
.eyebrow { margin: 0; color: #84c99a; text-transform: uppercase; letter-spacing: .11em; font-size: .72rem; }
.top-actions { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.version, .nav-link { border: 1px solid #2d4838; border-radius: 999px; padding: 7px 10px; color: #b7cabc; text-decoration: none; font-size: .8rem; }
.nav-link:hover { border-color: #5a9d70; background: #122019; }
.principle { display: flex; gap: 12px; align-items: center; justify-content: space-between; border: 1px solid #294433; background: #101a14; border-radius: 12px; padding: 11px 13px; margin-bottom: 14px; }
.principle span { color: var(--muted); font-size: .84rem; max-width: 820px; }
.layout { display: grid; grid-template-columns: minmax(260px, 330px) minmax(0, 1fr) minmax(230px, 290px); gap: 12px; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: 13px; box-shadow: 0 18px 55px rgba(0,0,0,.2); min-width: 0; }
.panel-head, .feature-heading, .output-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.label { display: block; font-weight: 700; font-size: .78rem; color: #b7c7bd; margin-bottom: 5px; }
.muted { color: var(--muted); line-height: 1.45; }
input, textarea, select { width: 100%; border: 1px solid #30453a; border-radius: 8px; background: #090e0b; color: #e8f0eb; padding: 9px 10px; }
input[type=checkbox] { width: auto; accent-color: var(--accent); }
select[multiple] { min-height: 116px; }
#feature-filter { margin-top: 10px; }
.chips { display: flex; gap: 5px; overflow: auto; padding: 8px 0; }
.chip { white-space: nowrap; border: 1px solid #2e4236; background: #0c120e; color: #aebfb4; border-radius: 999px; padding: 5px 8px; font-size: .72rem; cursor: pointer; }
.chip.active { background: var(--accent-soft); border-color: #4f8e63; color: #d8efe0; }
.feature-list { display: flex; flex-direction: column; gap: 6px; max-height: 68vh; overflow: auto; }
.feature { appearance: none; border: 1px solid #1f2d25; border-radius: 10px; background: var(--panel-soft); color: #d4e0d8; text-align: left; padding: 10px; cursor: pointer; }
.feature:hover, .feature.active { background: #17241c; border-color: #315640; }
.feature strong { display: block; font-size: .86rem; }
.feature small { display: block; color: #789184; margin-top: 4px; }
.runner h2 { margin: .15rem 0 .2rem; font-size: 1.28rem; }
.operation-category { margin: 0; color: #86a392; font-size: .78rem; }
.badge { white-space: nowrap; border: 1px solid #365443; border-radius: 999px; padding: 5px 8px; color: #a6cbb0; font-size: .69rem; }
.fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 12px 0; }
.field { border: 1px solid #223229; background: var(--panel-soft); border-radius: 10px; padding: 11px; }
.field.full { grid-column: 1 / -1; }
.field-head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 7px; }
.field-title { font-weight: 700; font-size: .83rem; }
.required { color: #d9b890; font-size: .7rem; }
.field-help { color: #83978a; font-size: .75rem; margin: 7px 0 0; line-height: 1.4; }
.use-option { display: flex; gap: 7px; align-items: center; color: #a8b9ae; font-size: .75rem; margin-bottom: 7px; }
.boolean-card { display: flex; gap: 9px; align-items: flex-start; padding: 8px 0; }
.boolean-card span { line-height: 1.35; }
.value-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 7px; }
.approval { margin: 12px 0; padding: 12px; border: 1px solid #654a28; background: #1c160e; border-radius: 10px; }
.approval-title { margin: 0 0 8px; font-weight: 750; color: #e0bf93; }
.check { display: flex; gap: 8px; align-items: flex-start; font-size: .84rem; margin: 7px 0; }
.destructive { color: #efc09e; }
.hidden { display: none !important; }
.actions { display: flex; gap: 8px; margin: 12px 0; }
button { border: 0; border-radius: 8px; padding: 9px 12px; background: var(--accent); color: #061008; font-weight: 750; cursor: pointer; }
button:disabled { opacity: .45; cursor: not-allowed; }
.secondary, .ghost { background: #17231c; color: #d2dfd6; border: 1px solid #30463a; }
.ghost { padding: 6px 8px; font-size: .72rem; }
.job-meta { color: #93ad9c; font-size: .78rem; min-height: 1.1rem; margin-bottom: 7px; }
.output-card { border: 1px solid #1c2821; border-radius: 10px; overflow: hidden; background: #050806; }
.output-head { padding: 8px 11px; border-bottom: 1px solid #1c2821; color: #8eaa98; font-size: .75rem; }
pre { margin: 0; min-height: 245px; max-height: 46vh; overflow: auto; padding: 11px; color: #cae7d2; font: 12.5px/1.5 ui-monospace, SFMono-Regular, Consolas, monospace; white-space: pre-wrap; word-break: break-word; }
.jobs-list { display: flex; flex-direction: column; gap: 7px; max-height: 68vh; overflow: auto; margin-top: 8px; }
.job { border: 1px solid #283a30; border-radius: 9px; padding: 8px; background: var(--panel-soft); text-align: left; color: #d4e0d8; }
.job strong { display: block; font-size: .78rem; }
.job small { display: block; color: #82998a; margin-top: 3px; }
.mobile-tabs { display: none; }
@media (max-width: 1080px) {
  .layout { grid-template-columns: minmax(240px, 310px) minmax(0, 1fr); }
  .jobs { grid-column: 1 / -1; }
  .jobs-list { max-height: 220px; display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); }
}
@media (max-width: 760px) {
  .app-shell { width: min(100% - 14px, 1500px); padding-top: 12px; }
  .topbar { align-items: flex-start; }
  .top-actions { max-width: 48%; }
  .principle { align-items: flex-start; flex-direction: column; }
  .mobile-tabs { display: flex; position: sticky; top: 0; z-index: 5; background: #090d0bf2; gap: 6px; padding: 5px 0 9px; }
  .mobile-tabs button { flex: 1; background: #142019; color: #cfe0d4; border: 1px solid #2c4235; }
  .layout { grid-template-columns: 1fr; }
  .panel { display: none; }
  .panel.mobile-active { display: block; }
  .catalog.mobile-active .feature-list { max-height: 58vh; }
  .fields { grid-template-columns: 1fr; }
  .jobs-list { display: flex; max-height: 58vh; }
  pre { min-height: 220px; max-height: 48vh; }
  .topbar h1 { font-size: 1.35rem; }
  .nav-link, .version { font-size: .7rem; padding: 5px 7px; }
}
"""


WORKBENCH_JS = r"""
(() => {
  "use strict";

  const token = document.querySelector('meta[name="sentinel-workbench-token"]').content;
  const filter = document.getElementById("feature-filter");
  const categoryFilters = document.getElementById("category-filters");
  const list = document.getElementById("feature-list");
  const count = document.getElementById("feature-count");
  const coverage = document.getElementById("coverage");
  const title = document.getElementById("feature-title");
  const categoryText = document.getElementById("feature-category");
  const help = document.getElementById("feature-help");
  const classification = document.getElementById("classification");
  const fields = document.getElementById("fields");
  const approvalBox = document.getElementById("approval-box");
  const approved = document.getElementById("approved");
  const destructiveWrap = document.getElementById("destructive-wrap");
  const destructiveConfirmed = document.getElementById("destructive-confirmed");
  const run = document.getElementById("run");
  const cancel = document.getElementById("cancel");
  const meta = document.getElementById("job-meta");
  const output = document.getElementById("output");
  const outputState = document.getElementById("output-state");
  const jobsList = document.getElementById("jobs-list");
  const refreshJobs = document.getElementById("refresh-jobs");

  let catalog = [];
  let current = null;
  let selectedCategory = "all";
  let currentJob = null;
  let source = null;

  function humanize(value) {
    return String(value || "")
      .split(/\s+/)
      .map(part => part.replace(/-/g, " ").replace(/\b\w/g, ch => ch.toUpperCase()))
      .join(" ");
  }

  function splitMulti(value) {
    return value.split(/\r?\n/).map(item => item.trim()).filter(Boolean);
  }

  function operationTitle(path) {
    const match = catalog.find(item => item.path === path);
    return match ? match.title : humanize(path);
  }

  function renderCategories(data) {
    const groups = [{key: "all", label: "All"}, ...data.categories];
    categoryFilters.replaceChildren();
    groups.forEach(group => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "chip" + (selectedCategory === group.key ? " active" : "");
      button.textContent = group.label;
      button.addEventListener("click", () => {
        selectedCategory = group.key;
        renderCategories(data);
        renderFeatures();
      });
      categoryFilters.append(button);
    });
  }

  function renderFeatures() {
    const q = filter.value.trim().toLowerCase();
    list.replaceChildren();
    const visible = catalog.filter(item => {
      const categoryMatch = selectedCategory === "all" || item.category === selectedCategory;
      const searchMatch = !q || item.title.toLowerCase().includes(q) ||
        item.help.toLowerCase().includes(q) || item.category_label.toLowerCase().includes(q) ||
        item.path.toLowerCase().includes(q);
      return categoryMatch && searchMatch;
    });
    count.textContent = `${visible.length}/${catalog.length}`;
    visible.forEach(item => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "feature" + (current && current.path === item.path ? " active" : "");
      button.setAttribute("role", "option");
      button.setAttribute("aria-selected", current && current.path === item.path ? "true" : "false");
      const strong = document.createElement("strong");
      strong.textContent = item.title;
      const small = document.createElement("small");
      small.textContent = `${item.category_label} · ${item.context_only ? "Web context" : item.classification}`;
      button.append(strong, small);
      button.addEventListener("click", () => selectFeature(item));
      list.append(button);
    });
  }

  function addOption(select, value, text) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = String(text);
    select.append(option);
  }

  function createValueControl(param) {
    let control;
    if (param.control === "tri-state") {
      control = document.createElement("select");
      addOption(control, "default", "Use recommended default");
      addOption(control, "enable", "Enabled");
      addOption(control, "disable", "Disabled");
    } else if (param.control === "flag") {
      control = document.createElement("input");
      control.type = "checkbox";
    } else if (param.control === "select" || param.control === "multi-select") {
      control = document.createElement("select");
      if (param.control === "multi-select") control.multiple = true;
      if (!param.required && param.control === "select") addOption(control, "", "Use default");
      param.choices.forEach(choice => addOption(control, choice, choice));
      if (param.default !== null && param.default !== undefined && param.control === "select") {
        control.value = String(param.default);
      }
    } else if (param.control === "multi-text") {
      control = document.createElement("textarea");
      control.rows = 4;
      control.placeholder = "One value per line";
    } else if (param.control === "multi-value") {
      control = document.createElement("div");
      control.className = "value-grid";
      for (let i = 0; i < param.nargs; i += 1) {
        const input = document.createElement("input");
        input.type = param.sensitive ? "password" : "text";
        input.autocomplete = param.sensitive ? "new-password" : "off";
        input.placeholder = `Value ${i + 1}`;
        input.dataset.role = "tuple-value";
        control.append(input);
      }
    } else {
      control = document.createElement("input");
      control.type = param.sensitive ? "password" : (param.control === "number" ? "number" : "text");
      control.autocomplete = param.sensitive ? "new-password" : "off";
      if (param.control === "path") control.placeholder = "Local path";
      if (param.control === "number") {
        if (param.min !== null && param.min !== undefined) control.min = String(param.min);
        if (param.max !== null && param.max !== undefined) control.max = String(param.max);
      }
      if (param.default !== null && param.default !== undefined && param.required) {
        control.value = String(param.default);
      }
    }
    return control;
  }

  function createField(param) {
    const box = document.createElement("div");
    box.className = "field" + ((param.multiple || param.nargs !== 1 || param.control === "multi-select") ? " full" : "");
    box.dataset.paramId = param.id;

    const head = document.createElement("div");
    head.className = "field-head";
    const fieldTitle = document.createElement("span");
    fieldTitle.className = "field-title";
    fieldTitle.textContent = param.label;
    head.append(fieldTitle);
    if (param.required) {
      const required = document.createElement("span");
      required.className = "required";
      required.textContent = "Required";
      head.append(required);
    }
    box.append(head);

    if (param.kind === "option" && !param.is_flag && !param.count && !param.required) {
      const use = document.createElement("label");
      use.className = "use-option";
      const include = document.createElement("input");
      include.type = "checkbox";
      include.dataset.role = "include";
      const text = document.createElement("span");
      text.textContent = "Customize this setting";
      use.append(include, text);
      box.append(use);
    }

    let control = createValueControl(param);
    if (param.control === "flag") {
      const label = document.createElement("label");
      label.className = "boolean-card";
      control.dataset.role = "value";
      const text = document.createElement("span");
      text.textContent = param.help || `Enable ${param.label}`;
      label.append(control, text);
      box.append(label);
    } else if (param.control === "multi-value") {
      control.dataset.role = "value-group";
      box.append(control);
    } else {
      control.dataset.role = "value";
      if (param.required && param.kind === "argument") control.required = true;
      box.append(control);
    }

    if (param.count) {
      control.type = "number";
      control.min = "0";
      control.step = "1";
      control.value = "0";
    }

    const desc = document.createElement("p");
    desc.className = "field-help";
    if (param.help) {
      desc.textContent = param.help;
    } else if (param.control === "path") {
      desc.textContent = "Select or enter the local workspace/resource path used by this operation.";
    } else if (param.default !== null && param.default !== undefined) {
      desc.textContent = `Default: ${String(param.default)}`;
    } else {
      desc.textContent = "Configure this value for the selected operation.";
    }
    box.append(desc);
    return box;
  }

  function showMobile(name) {
    if (!window.matchMedia("(max-width: 760px)").matches) return;
    document.querySelectorAll(".panel").forEach(panel => panel.classList.remove("mobile-active"));
    const target = name === "catalog" ? document.getElementById("catalog-panel") :
      name === "jobs" ? document.getElementById("jobs-panel") : document.getElementById("runner-panel");
    target.classList.add("mobile-active");
  }

  function selectFeature(item) {
    current = item;
    title.textContent = item.title;
    categoryText.textContent = item.category_label;
    help.textContent = item.help || "Configure the operation using the controls below.";
    classification.textContent = item.classification;
    fields.replaceChildren();
    item.params.forEach(param => fields.append(createField(param)));
    approvalBox.classList.toggle("hidden", !item.approval_required);
    destructiveWrap.classList.toggle("hidden", !item.approval_phrase_required);
    approved.checked = false;
    destructiveConfirmed.checked = false;
    run.disabled = !item.executable;
    run.textContent = item.executable ? `Run ${item.title}` : "Available in current Web context";
    output.textContent = item.context_only ?
      "This capability is already active in the current Web-server context." : "Ready.";
    outputState.textContent = "";
    renderFeatures();
    showMobile("runner");
  }

  function valuesFor(param, box) {
    if (param.control === "multi-value") {
      return [...box.querySelectorAll('[data-role="tuple-value"]')].map(el => el.value.trim());
    }
    const control = box.querySelector('[data-role="value"]');
    if (!control) return [];
    if (param.control === "multi-text") return splitMulti(control.value);
    if (param.control === "multi-select") return [...control.selectedOptions].map(option => option.value);
    return [control.value];
  }

  function serializeCurrent() {
    if (!current) return [];
    const optionArgs = [];
    const positionalArgs = [];

    current.params.forEach(param => {
      const box = fields.querySelector(`[data-param-id="${CSS.escape(param.id)}"]`);
      if (!box) return;
      const include = box.querySelector('[data-role="include"]');
      const valueControl = box.querySelector('[data-role="value"]');

      if (param.kind === "option") {
        const opt = param.primary_opt;
        if (param.control === "tri-state") {
          if (valueControl.value === "enable" && opt) optionArgs.push(opt);
          if (valueControl.value === "disable" && param.negative_opt) optionArgs.push(param.negative_opt);
          return;
        }
        if (param.control === "flag") {
          if (valueControl && valueControl.checked && opt) optionArgs.push(opt);
          return;
        }
        if (param.count) {
          const n = Math.max(0, Number.parseInt(valueControl.value || "0", 10) || 0);
          for (let i = 0; i < n; i += 1) if (opt) optionArgs.push(opt);
          return;
        }
        if (include && !include.checked) return;
        if (!opt) throw new Error(`${param.label} cannot be mapped to the operation backend.`);
        const values = valuesFor(param, box);
        const nonEmpty = values.filter(value => value !== "");
        if (param.required && nonEmpty.length === 0) throw new Error(`${param.label} is required.`);
        if (param.nargs > 1 && nonEmpty.length !== param.nargs) {
          throw new Error(`${param.label} requires ${param.nargs} values.`);
        }
        if (param.control === "multi-select" || param.multiple) {
          nonEmpty.forEach(value => optionArgs.push(opt, value));
        } else if (nonEmpty.length) {
          optionArgs.push(opt, ...nonEmpty);
        }
        return;
      }

      const values = valuesFor(param, box).filter(value => value !== "");
      if (param.required && values.length === 0) throw new Error(`${param.label} is required.`);
      if (param.nargs > 1 && values.length !== param.nargs) {
        throw new Error(`${param.label} requires ${param.nargs} values.`);
      }
      positionalArgs.push(...values);
    });

    return [...optionArgs, ...positionalArgs];
  }

  function setJob(job) {
    currentJob = job.job_id;
    output.textContent = job.output || "";
    outputState.textContent = job.status;
    meta.textContent = `${job.status} · ${job.classification}${job.returncode === null ? "" : ` · exit ${job.returncode}`}${job.truncated ? " · output truncated" : ""}`;
    cancel.disabled = !["queued", "running"].includes(job.status);
    if (["succeeded", "failed", "cancelled", "timed_out"].includes(job.status)) {
      if (source) { source.close(); source = null; }
      run.disabled = !current || !current.executable;
      refreshJobList();
    }
  }

  function watchJob(jobId) {
    if (source) source.close();
    source = new EventSource(`/api/v1/console/jobs/${encodeURIComponent(jobId)}/events`);
    source.addEventListener("output", event => {
      const payload = JSON.parse(event.data);
      output.textContent += payload.chunk;
      output.scrollTop = output.scrollHeight;
    });
    source.addEventListener("status", async () => {
      const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`, {cache: "no-store"});
      if (response.ok) setJob(await response.json());
    });
    source.onerror = async () => {
      source.close();
      source = null;
      const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`, {cache: "no-store"});
      if (response.ok) setJob(await response.json());
    };
  }

  async function refreshJobList() {
    const response = await fetch("/api/v1/console/jobs", {cache: "no-store"});
    if (!response.ok) return;
    const jobs = await response.json();
    jobsList.replaceChildren();
    jobs.slice(0, 30).forEach(job => {
      const box = document.createElement("button");
      box.type = "button";
      box.className = "job";
      const strong = document.createElement("strong");
      strong.textContent = operationTitle(job.command);
      const small = document.createElement("small");
      small.textContent = `${job.status} · ${job.classification}`;
      box.append(strong, small);
      box.addEventListener("click", () => {
        setJob(job);
        if (["queued", "running"].includes(job.status)) watchJob(job.job_id);
        showMobile("runner");
      });
      jobsList.append(box);
    });
    if (!jobs.length) {
      const empty = document.createElement("p");
      empty.className = "muted";
      empty.textContent = "No activity yet.";
      jobsList.append(empty);
    }
  }

  run.addEventListener("click", async () => {
    if (!current || !current.executable) return;
    let argv;
    try {
      argv = serializeCurrent();
    } catch (error) {
      output.textContent = String(error.message || error);
      return;
    }
    if (current.approval_required && !approved.checked) {
      output.textContent = "Human approval is required before this operation can run.";
      return;
    }
    if (current.approval_phrase_required && !destructiveConfirmed.checked) {
      output.textContent = "Confirm the destructive-operation warning before continuing.";
      return;
    }

    run.disabled = true;
    output.textContent = "";
    outputState.textContent = "submitting";
    meta.textContent = "Submitting operation…";
    const approvalPhrase = current.approval_phrase_required && destructiveConfirmed.checked ?
      `APPROVE ${current.path}` : null;
    const response = await fetch("/api/v1/console/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Sentinel-Console-Token": token},
      body: JSON.stringify({
        command: current.path,
        args: argv,
        approved: approved.checked,
        approval_phrase: approvalPhrase
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      output.textContent = payload.detail || "Operation rejected.";
      outputState.textContent = "rejected";
      meta.textContent = `HTTP ${response.status}`;
      run.disabled = false;
      return;
    }
    setJob(payload);
    watchJob(payload.job_id);
    refreshJobList();
  });

  cancel.addEventListener("click", async () => {
    if (!currentJob) return;
    const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(currentJob)}/cancel`, {
      method: "POST",
      headers: {"X-Sentinel-Console-Token": token}
    });
    if (response.ok) setJob(await response.json());
  });

  filter.addEventListener("input", renderFeatures);
  refreshJobs.addEventListener("click", refreshJobList);
  document.querySelectorAll("[data-mobile-target]").forEach(button =>
    button.addEventListener("click", () => showMobile(button.dataset.mobileTarget))
  );

  showMobile("catalog");
  fetch("/api/v1/workbench/catalog", {cache: "no-store"})
    .then(response => {
      if (!response.ok) throw new Error(`catalog HTTP ${response.status}`);
      return response.json();
    })
    .then(data => {
      catalog = data.features;
      coverage.textContent = data.contract.complete ? "Interface coverage complete" : "Coverage gap detected";
      coverage.style.color = data.contract.complete ? "#9fe1b0" : "#f2b58e";
      renderCategories(data);
      renderFeatures();
      if (catalog.length) selectFeature(catalog.find(item => item.path === "doctor") || catalog[0]);
    })
    .catch(error => {
      output.textContent = `Unable to load Security Console: ${error}`;
    });
  refreshJobList();
})();
"""


def mount_feature_workbench(
    app: FastAPI,
    config: WebConsoleConfig,
    manager: WebConsoleManager,
) -> None:
    """Mount a guided, responsive Web surface for every public product operation."""

    @app.get("/workbench", include_in_schema=False)
    async def workbench_page() -> HTMLResponse:
        return HTMLResponse(
            _workbench_html(config, manager.csrf_token),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/workbench/styles.css", include_in_schema=False)
    async def workbench_styles() -> PlainTextResponse:
        return PlainTextResponse(
            WORKBENCH_CSS,
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/workbench/app.js", include_in_schema=False)
    async def workbench_script() -> PlainTextResponse:
        return PlainTextResponse(
            WORKBENCH_JS,
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/workbench/catalog", tags=["web-workbench"])
    async def workbench_catalog() -> dict[str, Any]:
        features = build_feature_catalog(config.cli_module)
        categories = [
            {"key": key, "label": CATEGORY_LABELS[key]}
            for key in CATEGORY_ORDER
            if any(item["category"] == key for item in features)
        ]
        return {
            "schema_version": WORKBENCH_SCHEMA_VERSION,
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
    async def workbench_coverage() -> dict[str, Any]:
        return feature_contract(config.cli_module)
