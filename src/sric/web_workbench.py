from __future__ import annotations

import hashlib
import html
import json
import re
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse

from .web_console import WebConsoleConfig, WebConsoleManager, build_command_catalog

WORKBENCH_SCHEMA_VERSION = 1
SENSITIVE_MARKERS = (
    "token", "secret", "password", "passwd", "pwd", "cookie",
    "authorization", "api-key", "api_key", "apikey", "private-key", "private_key",
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
        "analyze", "analysis", "graph", "timeline", "search", "query", "inspect",
        "diff", "matrix", "findings", "coverage", "fossils", "lifecycle", "history",
        "explain", "assumptions", "lineage", "notebook", "reobserve", "reobservation",
        "evolution", "correlate",
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
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "command"


def _is_sensitive(name: str) -> bool:
    normalized = name.lower().replace("_", "-")
    return any(marker.replace("_", "-") in normalized for marker in SENSITIVE_MARKERS)


def _control_for(param: dict[str, Any]) -> str:
    if param.get("kind") == "option" and param.get("is_flag"):
        return "tri-state" if param.get("secondary_opts") else "flag"
    if param.get("count"):
        return "count"
    if param.get("multiple") or int(param.get("nargs", 1)) < 0:
        return "multi-text"
    type_name = str(param.get("type") or "").lower()
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
        "control": _control_for(param),
        "sensitive": _is_sensitive(name) or any(_is_sensitive(opt) for opt in opts),
    }


def build_feature_catalog(cli_module: str) -> list[dict[str, Any]]:
    """Create the structured Web feature schema from the real installed CLI tree."""
    features: list[dict[str, Any]] = []
    for command in build_command_catalog(cli_module):
        path = str(command["path"])
        category = _category(path)
        features.append({
            "id": _slug(path),
            "path": path,
            "title": path.replace("-", " ").title(),
            "help": str(command.get("help") or ""),
            "category": category,
            "category_label": CATEGORY_LABELS[category],
            "classification": str(command.get("classification") or "UNKNOWN"),
            "approval_required": bool(command.get("approval_required")),
            "approval_phrase_required": bool(command.get("approval_phrase_required")),
            "context_only": bool(command.get("context_only")),
            "executable": bool(command.get("executable")),
            "is_group": bool(command.get("is_group")),
            "params": [_web_param(param, i) for i, param in enumerate(command.get("params", []))],
            "web_surface": "context" if command.get("context_only") else "structured-form",
        })
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
    return f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><meta name='sentinel-workbench-token' content='{html.escape(csrf_token, quote=True)}'><title>{html.escape(config.display_name)} Web Workbench</title><link rel='stylesheet' href='/workbench/styles.css'></head><body><div class='app-shell'><header class='topbar'><div><p class='eyebrow'>Sentinel Forge · full Web/CLI feature parity</p><h1>{html.escape(config.display_name)}</h1></div><div class='top-actions'><span class='version'>v{html.escape(config.version)}</span><a href='/' class='nav-link'>Dashboard</a><a href='/console' class='nav-link'>Advanced console</a></div></header><section class='principle'><strong>AI proposes. Evidence proves. Humans control.</strong><span>Every public CLI command and argument is represented here. Product Scope/Policy/Approval controls remain authoritative.</span></section><div class='mobile-tabs'><button type='button' data-mobile-target='catalog'>Features</button><button type='button' data-mobile-target='runner'>Runner</button><button type='button' data-mobile-target='jobs'>Jobs</button></div><main class='layout'><aside class='panel catalog' id='catalog-panel'><div class='panel-head'><div><span class='label'>Features</span><strong id='coverage'>Loading…</strong></div><span id='feature-count' class='muted'></span></div><input id='feature-filter' type='search' placeholder='Search every feature or command' autocomplete='off'><div id='category-filters' class='chips'></div><div id='feature-list' class='feature-list' role='listbox'></div></aside><section class='panel runner' id='runner-panel'><div class='feature-heading'><div><span class='label'>Selected feature</span><h2 id='feature-title'>Select a feature</h2><code id='feature-path'></code></div><span id='classification' class='badge'>—</span></div><p id='feature-help' class='muted'></p><form id='feature-form' novalidate><div id='fields' class='fields'></div></form><details class='advanced'><summary>Advanced argv</summary><label for='extra-args'>Additional arguments</label><input id='extra-args' type='text' placeholder='Example: --json' autocomplete='off' spellcheck='false'><p class='hint'>Optional escape hatch for forward-compatible CLI syntax. It is tokenized as argv; no shell is invoked.</p></details><div id='approval-box' class='approval hidden'><label class='check'><input id='approved' type='checkbox'> I approve this mutating operation.</label><div id='phrase-wrap' class='hidden'><label for='approval-phrase'>Approval phrase</label><input id='approval-phrase' type='text' autocomplete='off'><code id='approval-expected'></code></div></div><div class='actions'><button id='run' type='button' disabled>Run feature</button><button id='cancel' type='button' class='secondary' disabled>Cancel</button></div><div id='job-meta' class='job-meta'></div><pre id='output' aria-live='polite' tabindex='0'>Select a feature to begin.</pre></section><aside class='panel jobs' id='jobs-panel'><div class='panel-head'><span class='label'>Recent jobs</span><button id='refresh-jobs' type='button' class='ghost'>Refresh</button></div><div id='jobs-list' class='jobs-list'></div></aside></main></div><script src='/workbench/app.js' defer></script></body></html>"""


WORKBENCH_CSS = r""":root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark;background:#090d0b;color:#e8f0eb;--panel:#101612;--line:#26352c;--muted:#8fa397;--accent:#78c38d;--accent2:#b9f1c8}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at top right,#163323 0,#090d0b 34rem)}a{color:inherit}.app-shell{width:min(1500px,calc(100% - 24px));margin:0 auto;padding:20px 0 36px}.topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:12px}.topbar h1{margin:.1rem 0;font-size:clamp(1.55rem,3vw,2.25rem)}.eyebrow{margin:0;color:#84c99a;text-transform:uppercase;letter-spacing:.11em;font-size:.72rem}.top-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.version,.nav-link{border:1px solid #2d4838;border-radius:999px;padding:7px 10px;color:#b7cabc;text-decoration:none;font-size:.8rem}.nav-link:hover{border-color:#5a9d70;background:#122019}.principle{display:flex;gap:12px;align-items:center;justify-content:space-between;border:1px solid #294433;background:#101a14;border-radius:12px;padding:11px 13px;margin-bottom:14px}.principle span{color:var(--muted);font-size:.84rem}.layout{display:grid;grid-template-columns:minmax(250px,330px) minmax(0,1fr) minmax(220px,290px);gap:12px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:13px;box-shadow:0 18px 55px rgba(0,0,0,.2);min-width:0}.panel-head,.feature-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}.label{display:block;font-weight:700;font-size:.78rem;color:#b7c7bd;margin-bottom:5px}.muted,.hint{color:var(--muted);line-height:1.45}.hint{font-size:.77rem;margin:.35rem 0 0}input,textarea,select{width:100%;border:1px solid #30453a;border-radius:8px;background:#090e0b;color:#e8f0eb;padding:9px 10px;outline:none}input:focus,textarea:focus,select:focus{border-color:#63ad79;box-shadow:0 0 0 3px rgba(99,173,121,.12)}input[type=checkbox]{width:auto;accent-color:var(--accent)}#feature-filter{margin-top:10px}.chips{display:flex;gap:5px;overflow:auto;padding:8px 0}.chip{white-space:nowrap;border:1px solid #2e4236;background:#0c120e;color:#aebfb4;border-radius:999px;padding:5px 8px;font-size:.72rem;cursor:pointer}.chip.active{background:#173021;border-color:#4f8e63;color:#d8efe0}.feature-list{display:flex;flex-direction:column;gap:5px;max-height:68vh;overflow:auto}.feature{appearance:none;border:1px solid transparent;border-radius:9px;background:transparent;color:#d4e0d8;text-align:left;padding:9px;cursor:pointer}.feature:hover,.feature.active{background:#17241c;border-color:#315640}.feature strong{display:block}.feature small{display:block;color:#789184;margin-top:3px}.runner h2{margin:.15rem 0 .2rem;font-size:1.25rem}.runner code{color:var(--accent2);font-size:.8rem}.badge{white-space:nowrap;border:1px solid #365443;border-radius:999px;padding:5px 8px;color:#a6cbb0;font-size:.69rem}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:12px 0}.field{border:1px solid #223229;background:#0c120e;border-radius:10px;padding:10px}.field.full{grid-column:1/-1}.field-head{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}.field-title{font-weight:700;font-size:.83rem}.field code{font-size:.68rem;color:#97b4a0}.field-help{color:#83978a;font-size:.75rem;margin:6px 0 0}.use-option{display:flex;gap:6px;align-items:center;color:#9bb0a2;font-size:.72rem}.advanced{border-top:1px solid #24342a;padding-top:10px;margin-top:8px}.advanced summary{cursor:pointer;color:#a9baaf;margin-bottom:8px}.approval{margin:12px 0;padding:11px;border:1px solid #654a28;background:#1c160e;border-radius:10px}.check{display:flex;gap:8px;align-items:center;font-size:.84rem}.hidden{display:none!important}.actions{display:flex;gap:8px;margin:12px 0}button{border:0;border-radius:8px;padding:9px 12px;background:var(--accent);color:#061008;font-weight:750;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.secondary,.ghost{background:#17231c;color:#d2dfd6;border:1px solid #30463a}.ghost{padding:6px 8px;font-size:.72rem}.job-meta{color:#93ad9c;font-size:.78rem;min-height:1.1rem;margin-bottom:6px}pre{margin:0;background:#050806;border:1px solid #1c2821;border-radius:10px;min-height:260px;max-height:46vh;overflow:auto;padding:11px;color:#cae7d2;font:12.5px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;word-break:break-word}.jobs-list{display:flex;flex-direction:column;gap:7px;max-height:68vh;overflow:auto;margin-top:8px}.job{border:1px solid #283a30;border-radius:9px;padding:8px;background:#0c120e;text-align:left;color:#d4e0d8}.job strong{display:block;font-size:.78rem}.job small{display:block;color:#82998a;margin-top:3px}.mobile-tabs{display:none}@media(max-width:1080px){.layout{grid-template-columns:minmax(240px,310px) minmax(0,1fr)}.jobs{grid-column:1/-1}.jobs-list{max-height:220px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}}@media(max-width:760px){.app-shell{width:min(100% - 14px,1500px);padding-top:12px}.topbar{align-items:flex-start}.top-actions{max-width:46%}.principle{align-items:flex-start;flex-direction:column}.mobile-tabs{display:flex;position:sticky;top:0;z-index:5;background:#090d0bf2;gap:6px;padding:5px 0 9px}.mobile-tabs button{flex:1;background:#142019;color:#cfe0d4;border:1px solid #2c4235}.layout{grid-template-columns:1fr}.panel{display:none}.panel.mobile-active{display:block}.catalog.mobile-active .feature-list{max-height:58vh}.fields{grid-template-columns:1fr}.jobs-list{display:flex;max-height:58vh}pre{min-height:220px;max-height:48vh}.topbar h1{font-size:1.35rem}.nav-link,.version{font-size:.7rem;padding:5px 7px}}"""


WORKBENCH_JS = r"""(() => {"use strict";const token=document.querySelector('meta[name="sentinel-workbench-token"]').content;const filter=document.getElementById("feature-filter"),categoryFilters=document.getElementById("category-filters"),list=document.getElementById("feature-list"),count=document.getElementById("feature-count"),coverage=document.getElementById("coverage"),title=document.getElementById("feature-title"),path=document.getElementById("feature-path"),help=document.getElementById("feature-help"),classification=document.getElementById("classification"),fields=document.getElementById("fields"),extra=document.getElementById("extra-args"),approvalBox=document.getElementById("approval-box"),approved=document.getElementById("approved"),phraseWrap=document.getElementById("phrase-wrap"),phrase=document.getElementById("approval-phrase"),expected=document.getElementById("approval-expected"),run=document.getElementById("run"),cancel=document.getElementById("cancel"),meta=document.getElementById("job-meta"),output=document.getElementById("output"),jobsList=document.getElementById("jobs-list"),refreshJobs=document.getElementById("refresh-jobs");let catalog=[],current=null,category="all",currentJob=null,source=null;function tokenize(text){const out=[];let buf="",quote=null;for(let i=0;i<text.length;i++){const ch=text[i];if(quote){if(ch===quote){quote=null;continue}if(ch==="\\"&&i+1<text.length&&text[i+1]===quote){buf+=quote;i++;continue}buf+=ch;continue}if(ch==='"'||ch==="'"){quote=ch;continue}if(/\s/.test(ch)){if(buf){out.push(buf);buf=""}continue}buf+=ch}if(quote)throw new Error("Unclosed quote in arguments");if(buf)out.push(buf);return out}function splitMulti(value){return value.split(/\r?\n/).map(v=>v.trim()).filter(Boolean)}function labelText(param){const names=param.kind==="option"&&param.opts.length?param.opts.join(", "):param.name;return `${names}${param.required?" *":""}`}function renderCategories(data){const groups=[{key:"all",label:"All"},...data.categories];categoryFilters.replaceChildren();groups.forEach(group=>{const button=document.createElement("button");button.type="button";button.className="chip"+(category===group.key?" active":"");button.textContent=group.label;button.addEventListener("click",()=>{category=group.key;renderCategories(data);renderFeatures()});categoryFilters.append(button)})}function renderFeatures(){const q=filter.value.trim().toLowerCase();list.replaceChildren();const visible=catalog.filter(item=>(category==="all"||item.category===category)&&(!q||item.path.toLowerCase().includes(q)||item.help.toLowerCase().includes(q)||item.category_label.toLowerCase().includes(q)));count.textContent=`${visible.length}/${catalog.length}`;visible.forEach(item=>{const button=document.createElement("button");button.type="button";button.className="feature"+(current&&current.path===item.path?" active":"");const strong=document.createElement("strong");strong.textContent=item.path;const small=document.createElement("small");small.textContent=`${item.category_label} · ${item.context_only?"Web context":item.classification}`;button.append(strong,small);button.addEventListener("click",()=>selectFeature(item));list.append(button)})}function createField(param){const box=document.createElement("div");box.className="field"+((param.multiple||param.nargs!==1)?" full":"");box.dataset.paramId=param.id;const head=document.createElement("div");head.className="field-head";const fieldTitle=document.createElement("span");fieldTitle.className="field-title";fieldTitle.textContent=param.label;const code=document.createElement("code");code.textContent=labelText(param);head.append(fieldTitle,code);box.append(head);let control;if(param.control==="tri-state"){control=document.createElement("select");[["default","Use CLI default"],["enable",`Enable (${param.primary_opt||"flag"})`],["disable",`Disable (${param.negative_opt||"negative flag"})`]].forEach(([value,text])=>{const option=document.createElement("option");option.value=value;option.textContent=text;control.append(option)})}else if(param.control==="flag"){const label=document.createElement("label");label.className="check";control=document.createElement("input");control.type="checkbox";const text=document.createElement("span");text.textContent=param.primary_opt?`Use ${param.primary_opt}`:"Enabled";label.append(control,text);box.append(label)}else if(param.control==="multi-text"){control=document.createElement("textarea");control.rows=4;control.placeholder="One value per line"}else{control=document.createElement("input");control.type=param.sensitive?"password":(param.control==="number"?"number":"text");control.autocomplete=param.sensitive?"new-password":"off";if(param.default!==null&&param.default!==undefined&&param.required)control.value=String(param.default)}if(control){control.dataset.role="value";if(param.required&&param.kind==="argument")control.required=true;if(!box.contains(control))box.append(control)}if(param.kind==="option"&&!param.is_flag&&!param.count){const use=document.createElement("label");use.className="use-option";const checkbox=document.createElement("input");checkbox.type="checkbox";checkbox.dataset.role="include";checkbox.checked=param.required;checkbox.disabled=param.required;const text=document.createElement("span");text.textContent=param.required?"Required option":"Include option";use.append(checkbox,text);box.insertBefore(use,control||null)}if(param.count){control.type="number";control.min="0";control.step="1";control.value="0";control.dataset.role="value"}const desc=document.createElement("p");desc.className="field-help";desc.textContent=param.help||`${param.type}${param.default!==null&&param.default!==undefined?` · default: ${String(param.default)}`:""}`;box.append(desc);return box}function showMobile(name){if(!window.matchMedia("(max-width: 760px)").matches)return;document.querySelectorAll(".panel").forEach(panel=>panel.classList.remove("mobile-active"));const target=name==="catalog"?document.getElementById("catalog-panel"):name==="jobs"?document.getElementById("jobs-panel"):document.getElementById("runner-panel");target.classList.add("mobile-active")}function selectFeature(item){current=item;title.textContent=item.title;path.textContent=item.path;help.textContent=item.help||"No additional CLI help text.";classification.textContent=item.classification;fields.replaceChildren();item.params.forEach(param=>fields.append(createField(param)));approvalBox.classList.toggle("hidden",!item.approval_required);phraseWrap.classList.toggle("hidden",!item.approval_phrase_required);approved.checked=false;phrase.value="";expected.textContent=item.approval_phrase_required?`APPROVE ${item.path}`:"";extra.value="";run.disabled=!item.executable;output.textContent=item.context_only?"This feature is already active in the current Web-server context.":"Ready.";renderFeatures();showMobile("runner")}function serializeCurrent(){if(!current)return[];const optionArgs=[],positionalArgs=[];current.params.forEach(param=>{const box=fields.querySelector(`[data-param-id="${CSS.escape(param.id)}"]`);if(!box)return;const valueControl=box.querySelector('[data-role="value"]'),include=box.querySelector('[data-role="include"]');if(param.kind==="option"){const opt=param.primary_opt;if(param.control==="tri-state"){if(valueControl.value==="enable"&&opt)optionArgs.push(opt);if(valueControl.value==="disable"&&param.negative_opt)optionArgs.push(param.negative_opt);return}if(param.control==="flag"){if(valueControl&&valueControl.checked&&opt)optionArgs.push(opt);return}if(param.count){const n=Math.max(0,Number.parseInt(valueControl.value||"0",10)||0);for(let i=0;i<n;i++)if(opt)optionArgs.push(opt);return}if(include&&!include.checked)return;if(!opt)throw new Error(`No CLI option name available for ${param.name}`);const values=param.control==="multi-text"?splitMulti(valueControl.value):[valueControl.value];if(param.required&&!values.some(Boolean))throw new Error(`${param.name} is required`);values.filter(v=>v!=="").forEach(value=>{optionArgs.push(opt);if(param.nargs>1){const tokens=tokenize(value);if(tokens.length!==param.nargs)throw new Error(`${param.name} expects ${param.nargs} values`);optionArgs.push(...tokens)}else optionArgs.push(value)});return}const values=param.control==="multi-text"?splitMulti(valueControl.value):[valueControl.value];if(param.required&&!values.some(Boolean))throw new Error(`${param.name} is required`);values.filter(v=>v!=="").forEach(value=>{if(param.nargs>1){const tokens=tokenize(value);if(tokens.length!==param.nargs)throw new Error(`${param.name} expects ${param.nargs} values`);positionalArgs.push(...tokens)}else positionalArgs.push(value)})});return[...optionArgs,...positionalArgs,...tokenize(extra.value)]}function setJob(job){currentJob=job.job_id;output.textContent=job.output||"";meta.textContent=`${job.status} · ${job.classification}${job.returncode===null?"":` · exit ${job.returncode}`}${job.truncated?" · truncated":""}`;cancel.disabled=!["queued","running"].includes(job.status);if(["succeeded","failed","cancelled","timed_out"].includes(job.status)){if(source){source.close();source=null}run.disabled=!current||!current.executable;refreshJobList()}}function watchJob(jobId){if(source)source.close();source=new EventSource(`/api/v1/console/jobs/${encodeURIComponent(jobId)}/events`);source.addEventListener("output",event=>{const payload=JSON.parse(event.data);output.textContent+=payload.chunk;output.scrollTop=output.scrollHeight});source.addEventListener("status",async()=>{const response=await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`,{cache:"no-store"});if(response.ok)setJob(await response.json())});source.onerror=async()=>{source.close();source=null;const response=await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`,{cache:"no-store"});if(response.ok)setJob(await response.json())}}async function refreshJobList(){const response=await fetch("/api/v1/console/jobs",{cache:"no-store"});if(!response.ok)return;const jobs=await response.json();jobsList.replaceChildren();jobs.slice(0,30).forEach(job=>{const box=document.createElement("button");box.type="button";box.className="job";const strong=document.createElement("strong");strong.textContent=job.command;const small=document.createElement("small");small.textContent=`${job.status} · ${job.classification}`;box.append(strong,small);box.addEventListener("click",()=>{setJob(job);if(["queued","running"].includes(job.status))watchJob(job.job_id);showMobile("runner")});jobsList.append(box)});if(!jobs.length){const empty=document.createElement("p");empty.className="muted";empty.textContent="No jobs yet.";jobsList.append(empty)}}run.addEventListener("click",async()=>{if(!current||!current.executable)return;let argv;try{argv=serializeCurrent()}catch(err){output.textContent=String(err.message||err);return}run.disabled=true;output.textContent="";meta.textContent="Submitting…";const response=await fetch("/api/v1/console/jobs",{method:"POST",headers:{"Content-Type":"application/json","X-Sentinel-Console-Token":token},body:JSON.stringify({command:current.path,args:argv,approved:approved.checked,approval_phrase:phrase.value||null})});const payload=await response.json();if(!response.ok){output.textContent=payload.detail||"Feature rejected.";meta.textContent=`HTTP ${response.status}`;run.disabled=false;return}setJob(payload);watchJob(payload.job_id);refreshJobList()});cancel.addEventListener("click",async()=>{if(!currentJob)return;const response=await fetch(`/api/v1/console/jobs/${encodeURIComponent(currentJob)}/cancel`,{method:"POST",headers:{"X-Sentinel-Console-Token":token}});if(response.ok)setJob(await response.json())});filter.addEventListener("input",renderFeatures);refreshJobs.addEventListener("click",refreshJobList);document.querySelectorAll("[data-mobile-target]").forEach(button=>button.addEventListener("click",()=>showMobile(button.dataset.mobileTarget)));showMobile("catalog");fetch("/api/v1/workbench/catalog",{cache:"no-store"}).then(response=>{if(!response.ok)throw new Error(`catalog HTTP ${response.status}`);return response.json()}).then(data=>{catalog=data.features;coverage.textContent=data.contract.complete?"100% CLI/Web contract":"Parity gap detected";coverage.style.color=data.contract.complete?"#9fe1b0":"#f2b58e";renderCategories(data);renderFeatures();if(catalog.length)selectFeature(catalog.find(item=>item.path==="doctor")||catalog[0])}).catch(err=>{output.textContent=`Unable to load Web Workbench: ${err}`});refreshJobList()})();"""


def mount_feature_workbench(app: FastAPI, config: WebConsoleConfig, manager: WebConsoleManager) -> None:
    """Mount a structured, responsive Web surface for every public CLI feature."""
    @app.get("/workbench", include_in_schema=False)
    async def workbench_page() -> HTMLResponse:
        return HTMLResponse(_workbench_html(config, manager.csrf_token), headers={"Cache-Control": "no-store"})

    @app.get("/workbench/styles.css", include_in_schema=False)
    async def workbench_styles() -> PlainTextResponse:
        return PlainTextResponse(WORKBENCH_CSS, media_type="text/css", headers={"Cache-Control": "no-store"})

    @app.get("/workbench/app.js", include_in_schema=False)
    async def workbench_script() -> PlainTextResponse:
        return PlainTextResponse(WORKBENCH_JS, media_type="application/javascript", headers={"Cache-Control": "no-store"})

    @app.get("/api/v1/workbench/catalog", tags=["web-workbench"])
    async def workbench_catalog() -> dict[str, Any]:
        features = build_feature_catalog(config.cli_module)
        categories = [{"key": key, "label": CATEGORY_LABELS[key]} for key in CATEGORY_ORDER if any(item["category"] == key for item in features)]
        return {
            "schema_version": WORKBENCH_SCHEMA_VERSION,
            "product": config.product,
            "display_name": config.display_name,
            "version": config.version,
            "features": features,
            "categories": categories,
            "contract": feature_contract(config.cli_module),
            "execution": {"backend": "web-console-fixed-runner", "shell": False, "arbitrary_executable": False, "mutations_require_approval": True},
        }

    @app.get("/api/v1/workbench/coverage", tags=["web-workbench"])
    async def workbench_coverage() -> dict[str, Any]:
        return feature_contract(config.cli_module)
