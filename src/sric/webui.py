from __future__ import annotations

import html
import json
from dataclasses import dataclass

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response


@dataclass(frozen=True)
class AnalysisPage:
    title: str
    description: str
    endpoint: str
    example_payload: dict[str, object]
    caution: str = "Analysis does not validate a finding unless deterministic evidence does so."


def _page_html(config: AnalysisPage, *, prefix: str) -> str:
    example = json.dumps(
        config.example_payload,
        indent=2,
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    bootstrap = json.dumps(
        {"endpoint": config.endpoint, "example": config.example_payload},
        ensure_ascii=False,
    ).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(config.title)}</title>
  <link rel="stylesheet" href="{prefix}/styles.css">
</head>
<body>
  <main class="shell">
    <header class="hero">
      <div>
        <p class="eyebrow">Sentinel Forge · Evidence-Native Research</p>
        <h1>{html.escape(config.title)}</h1>
        <p class="description">{html.escape(config.description)}</p>
      </div>
      <span class="state" aria-label="Analysis truth state policy">Evidence first</span>
    </header>
    <section class="notice" aria-label="Safety note">{html.escape(config.caution)}</section>
    <div class="workspace">
      <section class="panel">
        <div class="panel-head"><h2>Input</h2><code>{html.escape(config.endpoint)}</code></div>
        <label class="sr-only" for="payload">Analysis JSON payload</label>
        <textarea id="payload" spellcheck="false">{html.escape(example)}</textarea>
        <div class="actions">
          <button id="run" type="button">Run analysis</button>
          <button id="reset" type="button" class="secondary">Reset example</button>
        </div>
      </section>
      <section class="panel" aria-live="polite">
        <div class="panel-head"><h2>Evidence result</h2><span id="status">Idle</span></div>
        <pre id="result">No analysis executed.</pre>
      </section>
    </div>
  </main>
  <script>window.SENTINEL_ANALYSIS={bootstrap};</script>
  <script src="{prefix}/app.js"></script>
</body>
</html>"""


_CSS = """
:root{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color-scheme:dark;background:#0b0f14;color:#ecf2f8}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 15% 0,#172335 0,#0b0f14 42%)}.shell{width:min(1440px,100%);margin:auto;padding:clamp(18px,3vw,40px)}.hero{display:flex;gap:24px;align-items:flex-start;justify-content:space-between;margin-bottom:20px}.eyebrow{font-size:.78rem;letter-spacing:.12em;text-transform:uppercase;color:#9db0c6;margin:0 0 8px}h1{font-size:clamp(1.8rem,4vw,3.2rem);line-height:1.05;margin:0}.description{max-width:780px;color:#b7c4d3;line-height:1.6}.state{white-space:nowrap;border:1px solid #35506f;background:#101a27;border-radius:999px;padding:8px 12px;color:#cfe4ff}.notice{border:1px solid #3a4655;background:#111821;border-radius:12px;padding:12px 14px;color:#c8d3df;margin-bottom:16px}.workspace{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}.panel{min-width:0;border:1px solid #273241;background:rgba(15,21,29,.92);border-radius:16px;padding:16px;box-shadow:0 14px 42px rgba(0,0,0,.22)}.panel-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.panel h2{font-size:1rem;margin:0}.panel code,#status{font-size:.78rem;color:#9fb0c4;overflow-wrap:anywhere}textarea,pre{width:100%;min-height:440px;border:1px solid #2b3849;border-radius:10px;background:#080c11;color:#dbe9f7;padding:14px;font:13px/1.55 ui-monospace,SFMono-Regular,Consolas,monospace;overflow:auto}textarea:focus,button:focus-visible{outline:2px solid #8fc3ff;outline-offset:2px}.actions{display:flex;gap:10px;margin-top:12px}button{border:1px solid #476b95;border-radius:9px;background:#193859;color:#f5f9ff;padding:10px 14px;font-weight:700;cursor:pointer}button:hover{filter:brightness(1.15)}button.secondary{background:#141b24;border-color:#354252;color:#cdd8e5}.error{color:#ffb2b2}.ok{color:#a9e6bb}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}@media(max-width:820px){.hero{display:block}.state{display:inline-block;margin-top:8px}.workspace{grid-template-columns:1fr}textarea,pre{min-height:320px}}
"""

_JS = """
(()=>{const cfg=window.SENTINEL_ANALYSIS;const payload=document.getElementById('payload');const result=document.getElementById('result');const status=document.getElementById('status');const run=document.getElementById('run');const reset=document.getElementById('reset');function showState(text,kind){status.textContent=text;status.className=kind||''}reset.addEventListener('click',()=>{payload.value=JSON.stringify(cfg.example,null,2);result.textContent='No analysis executed.';showState('Idle','')});run.addEventListener('click',async()=>{let body;try{body=JSON.parse(payload.value)}catch(err){result.textContent='Invalid JSON: '+err.message;showState('Input error','error');return}run.disabled=true;showState('Running…','');try{const response=await fetch(cfg.endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const text=await response.text();let parsed;try{parsed=JSON.parse(text)}catch(_){parsed={status:response.status,body:text}}result.textContent=JSON.stringify(parsed,null,2);showState(response.ok?'Completed':'Request failed',response.ok?'ok':'error')}catch(err){result.textContent='Request failed: '+err.message;showState('Request failed','error')}finally{run.disabled=false}})})();
"""


def create_analysis_page_router(prefix: str, config: AnalysisPage) -> APIRouter:
    """Create a small functional UI bound to one real JSON analysis endpoint."""

    normalized = "/" + prefix.strip("/")
    router = APIRouter()

    @router.get(normalized, response_class=HTMLResponse, include_in_schema=False)
    async def analysis_page() -> str:
        return _page_html(config, prefix=normalized)

    @router.get(f"{normalized}/styles.css", include_in_schema=False)
    async def analysis_styles() -> Response:
        return Response(_CSS, media_type="text/css")

    @router.get(f"{normalized}/app.js", include_in_schema=False)
    async def analysis_script() -> Response:
        return Response(_JS, media_type="application/javascript")

    return router
