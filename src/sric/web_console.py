from __future__ import annotations

import asyncio
import html
import importlib
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from typer.main import get_command

from .redaction import SENSITIVE_KEYS, redact_text


TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}
ANSI_ESCAPE_RE = re.compile(r"\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
UNSAFE_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
SAFE_COMMAND_NAMES = {
    "version",
    "doctor",
    "help",
    "capabilities",
    "status",
    "list",
    "inspect",
    "verify",
    "check",
    "diff",
    "timeline",
    "matrix",
    "findings",
    "graph",
    "query",
    "report",
    "explain",
    "history",
    "fossils",
    "assumptions",
    "coverage",
    "search",
    "lineage",
}
CONSERVATIVE_MUTATING_COMMAND_NAMES = {
    "collect",
    "collect-url",
    "demo",
    "evidence",
    "extract",
    "jobs",
    "notebook",
    "report",
    "validate",
    "workspace",
}
READ_ONLY_WORKSPACE_ACTIONS = {"list", "show", "status"}
DESTRUCTIVE_COMMAND_NAMES = {
    "delete",
    "destroy",
    "purge",
    "remove",
    "uninstall",
    "rollback",
    "revoke",
}
MUTATING_COMMAND_NAMES = {
    "init",
    "create",
    "import",
    "capture",
    "replay",
    "redact",
    "pack",
    "sign",
    "update",
    "install",
    "enable",
    "disable",
    "config",
    "set",
    "write",
    "record",
    "add",
    "apply",
    "cancel",
    "export",
    "compile",
}
SENSITIVE_OPTION_MARKERS = (
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


class ConsoleRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command: str = Field(min_length=1, max_length=256)
    args: list[str] = Field(default_factory=list, max_length=128)
    approved: bool = False
    approval_phrase: str | None = Field(default=None, max_length=256)


@dataclass(frozen=True, slots=True)
class WebConsoleConfig:
    product: str
    display_name: str
    cli_module: str
    version: str
    max_concurrent_jobs: int = 2
    max_output_chars: int = 1_000_000
    max_runtime_seconds: int = 1800
    max_jobs: int = 100


@dataclass
class ConsoleJob:
    job_id: str
    command: str
    args: list[str]
    classification: str
    approval_required: bool
    created_at: float
    status: str = "queued"
    started_at: float | None = None
    finished_at: float | None = None
    returncode: int | None = None
    output: list[str] = field(default_factory=list)
    output_chars: int = 0
    truncated: bool = False
    cancel_requested: bool = False
    process: subprocess.Popen[str] | None = field(default=None, repr=False)


def _json_default(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (tuple, list, set)):
        return [_json_default(item) for item in value]
    return repr(value)


def _option_metadata(param: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": param.name,
        "required": bool(getattr(param, "required", False)),
        "multiple": bool(getattr(param, "multiple", False)),
        "nargs": int(getattr(param, "nargs", 1)),
        "default": _json_default(getattr(param, "default", None)),
        "type": getattr(
            getattr(param, "type", None),
            "name",
            type(getattr(param, "type", None)).__name__,
        ),
    }
    hint = str(getattr(param, "param_type_name", "") or "").lower()
    class_name = type(param).__name__.lower()
    is_option = hint == "option" or (
        hint != "argument" and class_name.endswith("option")
    )
    if is_option:
        payload.update(
            {
                "kind": "option",
                "opts": list(getattr(param, "opts", ()) or ()),
                "secondary_opts": list(getattr(param, "secondary_opts", ()) or ()),
                "help": getattr(param, "help", "") or "",
                "is_flag": bool(getattr(param, "is_flag", False)),
                "count": bool(getattr(param, "count", False)),
            }
        )
    else:
        payload.update(
            {"kind": "argument", "opts": [], "secondary_opts": [], "help": ""}
        )
    return payload


def _classify_command(path: tuple[str, ...]) -> tuple[str, bool, bool]:
    normalized = {part.lower().replace("_", "-") for part in path}
    if "web" in normalized:
        return "READ_ONLY_SAFE", False, True
    if normalized & DESTRUCTIVE_COMMAND_NAMES:
        return "MUTATING_DESTRUCTIVE", True, False
    if normalized & MUTATING_COMMAND_NAMES:
        return "MUTATING_REVERSIBLE", True, False
    ordered = tuple(part.lower().replace("_", "-") for part in path)
    if "workspace" in normalized:
        if len(ordered) > 1 and ordered[-1] in READ_ONLY_WORKSPACE_ACTIONS:
            return "READ_ONLY_SAFE", False, False
        return "MUTATING_REVERSIBLE", True, False
    if normalized & CONSERVATIVE_MUTATING_COMMAND_NAMES:
        return "MUTATING_REVERSIBLE", True, False
    if normalized and normalized <= SAFE_COMMAND_NAMES:
        return "READ_ONLY_SAFE", False, False
    return "READ_ONLY_SENSITIVE", False, False


def _load_root(cli_module: str) -> Any:
    module = importlib.import_module(cli_module)
    app = getattr(module, "app", None)
    if app is None:
        raise RuntimeError(f"{cli_module} does not expose a Typer app")
    return get_command(app)


def build_command_catalog(cli_module: str) -> list[dict[str, Any]]:
    root = _load_root(cli_module)
    commands: list[dict[str, Any]] = []

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        children = getattr(command, "commands", None)
        if isinstance(children, dict):
            for name, child in sorted(children.items()):
                if getattr(child, "hidden", False):
                    continue
                path = prefix + (name,)
                classification, approval_required, context_only = _classify_command(path)
                commands.append(
                    {
                        "path": " ".join(path),
                        "help": child.help or child.short_help or "",
                        "classification": classification,
                        "approval_required": approval_required,
                        "approval_phrase_required": classification
                        == "MUTATING_DESTRUCTIVE",
                        "context_only": context_only,
                        "executable": not context_only,
                        "is_group": isinstance(getattr(child, "commands", None), dict),
                        "params": [_option_metadata(param) for param in child.params],
                    }
                )
                walk(child, path)

    walk(root, ())
    return commands


def _normalize_option_name(value: str) -> str:
    return value.lstrip("-").strip().lower().replace("_", "-")


def _looks_sensitive_option(value: str) -> bool:
    normalized = _normalize_option_name(value)
    normalized_keys = {key.replace("_", "-") for key in SENSITIVE_KEYS}
    return normalized in normalized_keys or any(
        marker in normalized for marker in SENSITIVE_OPTION_MARKERS
    )


def redact_argv(args: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    counter = 0
    for raw in args:
        value = str(raw)
        if redact_next:
            counter += 1
            redacted.append(f"${{{{REDACTED_CLI_SECRET_{counter}}}}}")
            redact_next = False
            continue
        if value.startswith("--") and "=" in value:
            option, option_value = value.split("=", 1)
            if _looks_sensitive_option(option) and option_value:
                counter += 1
                redacted.append(
                    f"{option}=${{{{REDACTED_CLI_SECRET_{counter}}}}}"
                )
                continue
        redacted.append(value)
        if value.startswith("-") and _looks_sensitive_option(value):
            redact_next = True
    return redacted


def _validate_args(args: list[str]) -> list[str]:
    total = 0
    normalized: list[str] = []
    for item in args:
        if "\x00" in item:
            raise ValueError("NUL bytes are not allowed in CLI arguments")
        if len(item) > 8192:
            raise ValueError("individual CLI arguments are limited to 8192 characters")
        total += len(item)
        if total > 32_768:
            raise ValueError(
                "combined CLI arguments exceed the 32768-character limit"
            )
        normalized.append(item)
    return normalized


class WebConsoleManager:
    def __init__(self, config: WebConsoleConfig) -> None:
        self.config = config
        self.csrf_token = secrets.token_urlsafe(32)
        self._jobs: dict[str, ConsoleJob] = {}
        self._lock = threading.RLock()
        self._semaphore = threading.BoundedSemaphore(config.max_concurrent_jobs)
        self._catalog_cache: list[dict[str, Any]] | None = None

    def catalog(self) -> list[dict[str, Any]]:
        if self._catalog_cache is None:
            self._catalog_cache = build_command_catalog(self.config.cli_module)
        return [dict(item) for item in self._catalog_cache]

    def _catalog_item(self, path: str) -> dict[str, Any]:
        for item in self.catalog():
            if item["path"] == path:
                return item
        raise KeyError(path)

    def _prune(self) -> None:
        with self._lock:
            if len(self._jobs) <= self.config.max_jobs:
                return
            completed = sorted(
                (
                    job
                    for job in self._jobs.values()
                    if job.status in TERMINAL_STATES
                ),
                key=lambda job: job.finished_at or job.created_at,
            )
            for job in completed[: max(0, len(self._jobs) - self.config.max_jobs)]:
                self._jobs.pop(job.job_id, None)

    def submit(self, request: ConsoleRunRequest) -> ConsoleJob:
        command = request.command.strip()
        try:
            meta = self._catalog_item(command)
        except KeyError as exc:
            raise ValueError(
                "unknown CLI command; refresh the command catalog"
            ) from exc
        if meta["context_only"]:
            raise RuntimeError(
                "this command is context-only in the Web UI; the Web server is already running"
            )
        if meta["approval_required"] and not request.approved:
            raise PermissionError("explicit approval is required for this command")
        if meta["approval_phrase_required"]:
            expected = f"APPROVE {command}"
            if request.approval_phrase != expected:
                raise PermissionError(
                    f"approval phrase must exactly match: {expected}"
                )

        args = _validate_args(request.args)
        job = ConsoleJob(
            job_id=uuid.uuid4().hex,
            command=command,
            args=redact_argv(args),
            classification=str(meta["classification"]),
            approval_required=bool(meta["approval_required"]),
            created_at=time.time(),
        )
        with self._lock:
            self._jobs[job.job_id] = job
        self._prune()
        threading.Thread(
            target=self._run,
            args=(job.job_id, command.split() + args),
            daemon=True,
            name=f"sentinel-console-{job.job_id[:8]}",
        ).start()
        return job

    def _append_output(self, job: ConsoleJob, chunk: str) -> None:
        cleaned = ANSI_ESCAPE_RE.sub("", UNSAFE_CONTROL_RE.sub("", chunk))
        safe = redact_text(cleaned).text
        with self._lock:
            if job.truncated:
                return
            remaining = self.config.max_output_chars - job.output_chars
            if remaining <= 0:
                job.truncated = True
                return
            if len(safe) > remaining:
                safe = (
                    safe[:remaining]
                    + "\n[output truncated by Web Command Console]\n"
                )
                job.truncated = True
            job.output.append(safe)
            job.output_chars += len(safe)

    def _run(self, job_id: str, argv: list[str]) -> None:
        with self._semaphore:
            with self._lock:
                job = self._jobs[job_id]
                if job.cancel_requested:
                    job.status = "cancelled"
                    job.finished_at = time.time()
                    return
                job.status = "running"
                job.started_at = time.time()

            env = os.environ.copy()
            env["NO_COLOR"] = "1"
            env["SENTINEL_BANNER"] = "off"
            env["PYTHONUNBUFFERED"] = "1"
            env["SENTINEL_CLI_MODULE"] = self.config.cli_module
            env["SENTINEL_WEB_CONSOLE"] = "1"
            command = [sys.executable, "-m", "sric.web_console_runner", *argv]

            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    shell=False,
                    env=env,
                )
            except Exception as exc:
                self._append_output(
                    job,
                    f"Unable to start CLI command: {type(exc).__name__}: {exc}\n",
                )
                with self._lock:
                    job.status = "failed"
                    job.finished_at = time.time()
                return

            with self._lock:
                job.process = process

            def reader() -> None:
                if process.stdout is None:
                    return
                for line in process.stdout:
                    self._append_output(job, line)

            reader_thread = threading.Thread(target=reader, daemon=True)
            reader_thread.start()
            timed_out = False
            try:
                returncode = process.wait(
                    timeout=self.config.max_runtime_seconds
                )
            except subprocess.TimeoutExpired:
                timed_out = True
                process.terminate()
                try:
                    returncode = process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    returncode = process.wait(timeout=5)
            reader_thread.join(timeout=2)

            with self._lock:
                job.returncode = returncode
                job.process = None
                job.finished_at = time.time()
                if timed_out:
                    job.status = "timed_out"
                elif job.cancel_requested:
                    job.status = "cancelled"
                elif returncode == 0:
                    job.status = "succeeded"
                else:
                    job.status = "failed"

    def cancel(self, job_id: str) -> ConsoleJob:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.status in TERMINAL_STATES:
                return job
            job.cancel_requested = True
            process = job.process
            if job.status == "queued":
                job.status = "cancelled"
                job.finished_at = time.time()
        if process is not None and process.poll() is None:
            process.terminate()
        return job

    def snapshot(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return {
                "job_id": job.job_id,
                "command": job.command,
                "args": list(job.args),
                "classification": job.classification,
                "approval_required": job.approval_required,
                "status": job.status,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "finished_at": job.finished_at,
                "returncode": job.returncode,
                "output": "".join(job.output),
                "output_chunks": len(job.output),
                "truncated": job.truncated,
                "cancel_requested": job.cancel_requested,
            }

    def list_snapshots(self) -> list[dict[str, Any]]:
        with self._lock:
            ids = [
                job.job_id
                for job in sorted(
                    self._jobs.values(),
                    key=lambda item: item.created_at,
                    reverse=True,
                )
            ]
        return [self.snapshot(job_id) for job_id in ids]

    def output_since(
        self, job_id: str, cursor: int
    ) -> tuple[list[str], int, str]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            start = max(0, min(cursor, len(job.output)))
            chunks = list(job.output[start:])
            return chunks, len(job.output), job.status


def _console_html(config: WebConsoleConfig, csrf_token: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="sentinel-console-token" content="{html.escape(csrf_token, quote=True)}">
<title>{html.escape(config.display_name)} Command Console</title>
<link rel="stylesheet" href="/console/styles.css">
</head>
<body>
<main class="shell">
<header>
<div><p class="eyebrow">Sentinel Forge · Web/CLI parity</p><h1>{html.escape(config.display_name)} Command Console</h1></div>
<div class="version">v{html.escape(config.version)}</div>
</header>
<section class="notice" role="note">
<strong>Not an operating-system shell.</strong>
Commands are discovered from the installed CLI, arguments are passed as an argv array, and execution uses a fixed Python runner with <code>shell=False</code>. Mutating commands require explicit approval.
</section>
<div class="layout">
<aside class="panel commands">
<label for="filter">Commands</label>
<input id="filter" type="search" placeholder="Filter commands" autocomplete="off">
<div id="command-list" class="command-list" role="listbox" aria-label="CLI commands"></div>
</aside>
<section class="panel runner">
<div class="selected-row"><div><span class="label">Selected command</span><code id="selected-command">Select a command</code></div><span id="classification" class="badge">—</span></div>
<p id="command-help" class="muted"></p>
<div id="params" class="params"></div>
<label for="args">Additional arguments</label>
<input id="args" type="text" placeholder='Example: --workspace demo --json' autocomplete="off" spellcheck="false">
<p class="hint">Use quotes around arguments containing spaces. The browser tokenizes this field; no shell is invoked.</p>
<div id="approval-box" class="approval hidden">
<label class="check"><input id="approved" type="checkbox"> I approve this mutating operation.</label>
<div id="phrase-wrap" class="hidden">
<label for="approval-phrase">Approval phrase</label>
<input id="approval-phrase" type="text" autocomplete="off">
<code id="approval-expected"></code>
</div>
</div>
<div class="actions"><button id="run" disabled>Run command</button><button id="cancel" class="secondary" disabled>Cancel job</button></div>
<div id="job-meta" class="job-meta"></div>
<pre id="output" aria-live="polite" tabindex="0">Select a command to begin.</pre>
</section>
</div>
</main>
<script src="/console/app.js" defer></script>
</body>
</html>"""


CONSOLE_CSS = r"""
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark;background:#0b0f0d;color:#e5eee8}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#153023 0,#0b0f0d 36rem);min-height:100vh}
.shell{width:min(1280px,calc(100% - 32px));margin:0 auto;padding:28px 0 40px}
header{display:flex;align-items:flex-start;justify-content:space-between;gap:20px;margin-bottom:18px}h1{font-size:clamp(1.55rem,3vw,2.35rem);margin:.1rem 0}.eyebrow{margin:0;color:#84c99a;text-transform:uppercase;letter-spacing:.12em;font-size:.76rem}.version{border:1px solid #2a4434;border-radius:999px;padding:7px 11px;color:#a9c7b2}
.notice{border:1px solid #294433;background:#111a15;border-radius:12px;padding:12px 14px;margin:0 0 16px;line-height:1.45}
.layout{display:grid;grid-template-columns:minmax(250px,340px) 1fr;gap:16px}.panel{background:#0f1512;border:1px solid #25342b;border-radius:14px;padding:14px;box-shadow:0 18px 60px rgba(0,0,0,.22)}
label,.label{display:block;font-weight:650;font-size:.86rem;margin:0 0 7px}input[type="search"],input[type="text"]{width:100%;border:1px solid #30453a;border-radius:9px;background:#0a0f0c;color:#e7f3eb;padding:10px 11px;outline:none}input:focus{border-color:#63ad79;box-shadow:0 0 0 3px rgba(99,173,121,.12)}
.command-list{display:flex;flex-direction:column;gap:5px;max-height:66vh;overflow:auto;margin-top:10px}.command{appearance:none;border:1px solid transparent;background:transparent;color:#cfe0d4;text-align:left;padding:9px;border-radius:8px;cursor:pointer}.command:hover,.command.active{background:#17251d;border-color:#315640}.command small{display:block;color:#789484;margin-top:3px}
.selected-row{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.selected-row code{font-size:1rem;color:#b7efc7}.badge{white-space:nowrap;border:1px solid #365443;border-radius:999px;padding:5px 8px;color:#a6cbb0;font-size:.72rem}
.muted,.hint{color:#82988a;line-height:1.45}.hint{font-size:.78rem;margin-top:6px}.params{display:flex;flex-wrap:wrap;gap:6px;margin:10px 0 14px}.param{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;border:1px solid #2c4035;border-radius:7px;padding:4px 6px;color:#96b5a0}
.approval{margin:12px 0;padding:11px;border:1px solid #654a28;background:#1c160e;border-radius:10px}.check{display:flex;gap:8px;align-items:center}.check input{accent-color:#83c998}.hidden{display:none!important}
.actions{display:flex;gap:8px;margin:13px 0}button{border:0;border-radius:9px;padding:10px 14px;background:#6fc186;color:#07100a;font-weight:750;cursor:pointer}button:disabled{opacity:.45;cursor:not-allowed}.secondary{background:#1b2820;color:#c9dacd;border:1px solid #30463a}
.job-meta{color:#8cab97;font-size:.8rem;min-height:1.1rem;margin-bottom:7px}pre{margin:0;background:#060907;border:1px solid #1e2b24;border-radius:10px;min-height:300px;max-height:55vh;overflow:auto;padding:12px;color:#c9e8d2;font:13px/1.5 ui-monospace,SFMono-Regular,Consolas,monospace;white-space:pre-wrap;word-break:break-word}
@media(max-width:820px){.shell{width:min(100% - 20px,1280px);padding-top:18px}.layout{grid-template-columns:1fr}.command-list{max-height:240px}header{align-items:center}.selected-row{flex-direction:column}.badge{align-self:flex-start}pre{min-height:260px}}
"""


CONSOLE_JS = r"""
(() => {
  "use strict";
  const token = document.querySelector('meta[name="sentinel-console-token"]').content;
  const list = document.getElementById("command-list");
  const filter = document.getElementById("filter");
  const selected = document.getElementById("selected-command");
  const help = document.getElementById("command-help");
  const classification = document.getElementById("classification");
  const params = document.getElementById("params");
  const argsInput = document.getElementById("args");
  const approvalBox = document.getElementById("approval-box");
  const approved = document.getElementById("approved");
  const phraseWrap = document.getElementById("phrase-wrap");
  const phrase = document.getElementById("approval-phrase");
  const expected = document.getElementById("approval-expected");
  const run = document.getElementById("run");
  const cancel = document.getElementById("cancel");
  const output = document.getElementById("output");
  const meta = document.getElementById("job-meta");
  let catalog = [];
  let current = null;
  let currentJob = null;
  let source = null;

  function tokenize(text) {
    const out = [];
    let buf = "";
    let quote = null;
    for (let i = 0; i < text.length; i++) {
      const ch = text[i];
      if (quote) {
        if (ch === quote) { quote = null; continue; }
        if (ch === "\\" && i + 1 < text.length && text[i + 1] === quote) { buf += quote; i++; continue; }
        buf += ch;
        continue;
      }
      if (ch === '"' || ch === "'") { quote = ch; continue; }
      if (/\s/.test(ch)) {
        if (buf) { out.push(buf); buf = ""; }
        continue;
      }
      buf += ch;
    }
    if (quote) throw new Error("Unclosed quote in arguments");
    if (buf) out.push(buf);
    return out;
  }

  function renderCommands() {
    const q = filter.value.trim().toLowerCase();
    list.replaceChildren();
    catalog.filter(c => !q || c.path.toLowerCase().includes(q) || c.help.toLowerCase().includes(q)).forEach(c => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "command" + (current && current.path === c.path ? " active" : "");
      button.setAttribute("role", "option");
      const title = document.createElement("strong");
      title.textContent = c.path;
      const sub = document.createElement("small");
      sub.textContent = c.context_only ? "Web context only" : c.classification;
      button.append(title, sub);
      button.addEventListener("click", () => selectCommand(c));
      list.append(button);
    });
  }

  function selectCommand(command) {
    current = command;
    selected.textContent = command.path;
    help.textContent = command.help || "No additional help text.";
    classification.textContent = command.classification;
    params.replaceChildren();
    command.params.forEach(p => {
      const chip = document.createElement("span");
      chip.className = "param";
      chip.textContent = p.kind === "option" && p.opts.length ? p.opts.join(", ") : p.name;
      if (p.required) chip.textContent += " *";
      params.append(chip);
    });
    approvalBox.classList.toggle("hidden", !command.approval_required);
    phraseWrap.classList.toggle("hidden", !command.approval_phrase_required);
    approved.checked = false;
    phrase.value = "";
    expected.textContent = command.approval_phrase_required ? `APPROVE ${command.path}` : "";
    run.disabled = !command.executable;
    output.textContent = command.context_only
      ? "This command starts the Web server and is already active in this context."
      : "Ready.";
    renderCommands();
  }

  function setJobState(job) {
    currentJob = job.job_id;
    output.textContent = job.output || "";
    meta.textContent = `${job.status} · ${job.classification}${job.returncode === null ? "" : ` · exit ${job.returncode}`}${job.truncated ? " · output truncated" : ""}`;
    cancel.disabled = !["queued", "running"].includes(job.status);
    if (["succeeded", "failed", "cancelled", "timed_out"].includes(job.status)) {
      if (source) { source.close(); source = null; }
      run.disabled = !current || !current.executable;
    }
  }

  function watchJob(jobId) {
    if (source) source.close();
    source = new EventSource(`/api/v1/console/jobs/${encodeURIComponent(jobId)}/events`);
    source.addEventListener("output", ev => {
      const payload = JSON.parse(ev.data);
      output.textContent += payload.chunk;
      output.scrollTop = output.scrollHeight;
    });
    source.addEventListener("status", async () => {
      const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`, {cache: "no-store"});
      if (response.ok) setJobState(await response.json());
    });
    source.onerror = async () => {
      source.close();
      source = null;
      const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(jobId)}`, {cache: "no-store"});
      if (response.ok) setJobState(await response.json());
    };
  }

  run.addEventListener("click", async () => {
    if (!current || !current.executable) return;
    let argv;
    try { argv = tokenize(argsInput.value); }
    catch (err) { output.textContent = String(err.message || err); return; }
    run.disabled = true;
    output.textContent = "";
    meta.textContent = "Submitting…";
    const response = await fetch("/api/v1/console/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-Sentinel-Console-Token": token},
      body: JSON.stringify({
        command: current.path,
        args: argv,
        approved: approved.checked,
        approval_phrase: phrase.value || null
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      output.textContent = payload.detail || "Command rejected.";
      meta.textContent = `HTTP ${response.status}`;
      run.disabled = false;
      return;
    }
    setJobState(payload);
    watchJob(payload.job_id);
  });

  cancel.addEventListener("click", async () => {
    if (!currentJob) return;
    const response = await fetch(`/api/v1/console/jobs/${encodeURIComponent(currentJob)}/cancel`, {
      method: "POST",
      headers: {"X-Sentinel-Console-Token": token}
    });
    if (response.ok) setJobState(await response.json());
  });

  filter.addEventListener("input", renderCommands);

  fetch("/api/v1/console/catalog", {cache: "no-store"})
    .then(r => { if (!r.ok) throw new Error(`catalog HTTP ${r.status}`); return r.json(); })
    .then(data => {
      catalog = data.commands;
      renderCommands();
      if (catalog.length) selectCommand(catalog.find(c => c.path === "doctor") || catalog[0]);
    })
    .catch(err => { output.textContent = `Unable to load command catalog: ${err}`; });
})();
"""


def mount_web_console(app: FastAPI, config: WebConsoleConfig) -> WebConsoleManager:
    manager = WebConsoleManager(config)

    def require_token(value: str | None) -> None:
        if value is None or not secrets.compare_digest(value, manager.csrf_token):
            raise HTTPException(
                403, "invalid or missing Web Command Console token"
            )

    @app.get("/console", include_in_schema=False)
    async def console_page() -> HTMLResponse:
        return HTMLResponse(
            _console_html(config, manager.csrf_token),
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/console/styles.css", include_in_schema=False)
    async def console_styles() -> PlainTextResponse:
        return PlainTextResponse(
            CONSOLE_CSS,
            media_type="text/css",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/console/app.js", include_in_schema=False)
    async def console_script() -> PlainTextResponse:
        return PlainTextResponse(
            CONSOLE_JS,
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @app.get("/api/v1/console/catalog", tags=["web-console"])
    async def console_catalog() -> dict[str, Any]:
        return {
            "product": config.product,
            "display_name": config.display_name,
            "version": config.version,
            "commands": manager.catalog(),
            "execution": {
                "shell": False,
                "arbitrary_executable": False,
                "max_concurrent_jobs": config.max_concurrent_jobs,
                "max_output_chars": config.max_output_chars,
                "max_runtime_seconds": config.max_runtime_seconds,
                "mutations_require_approval": True,
            },
        }

    @app.post("/api/v1/console/jobs", tags=["web-console"], status_code=202)
    async def console_submit(
        payload: ConsoleRunRequest,
        x_sentinel_console_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_sentinel_console_token)
        try:
            job = manager.submit(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(409, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return manager.snapshot(job.job_id)

    @app.get("/api/v1/console/jobs", tags=["web-console"])
    async def console_jobs() -> list[dict[str, Any]]:
        return manager.list_snapshots()

    @app.get("/api/v1/console/jobs/{job_id}", tags=["web-console"])
    async def console_job(job_id: str) -> dict[str, Any]:
        try:
            return manager.snapshot(job_id)
        except KeyError as exc:
            raise HTTPException(404, "console job not found") from exc

    @app.post("/api/v1/console/jobs/{job_id}/cancel", tags=["web-console"])
    async def console_cancel(
        job_id: str,
        x_sentinel_console_token: str | None = Header(default=None),
    ) -> dict[str, Any]:
        require_token(x_sentinel_console_token)
        try:
            job = manager.cancel(job_id)
        except KeyError as exc:
            raise HTTPException(404, "console job not found") from exc
        return manager.snapshot(job.job_id)

    @app.get("/api/v1/console/jobs/{job_id}/events", tags=["web-console"])
    async def console_events(job_id: str, cursor: int = 0) -> StreamingResponse:
        try:
            manager.snapshot(job_id)
        except KeyError as exc:
            raise HTTPException(404, "console job not found") from exc

        async def stream() -> Any:
            current = max(0, cursor)
            while True:
                chunks, current, status = manager.output_since(job_id, current)
                for chunk in chunks:
                    yield (
                        "event: output\n"
                        f"data: {json.dumps({'chunk': chunk})}\n\n"
                    )
                yield (
                    "event: status\n"
                    f"data: {json.dumps({'status': status, 'cursor': current})}\n\n"
                )
                if status in TERMINAL_STATES:
                    break
                await asyncio.sleep(0.25)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-store",
                "X-Accel-Buffering": "no",
            },
        )

    return manager
