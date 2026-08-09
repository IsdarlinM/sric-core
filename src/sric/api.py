from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse

from . import __version__
from .graph import TemporalGraph
from .jobs import JobEngine
from .notebook import ResearchNotebook
from .query import SecurityResearchGraphQuery
from .web_console import WebConsoleConfig, mount_web_console
from .web_workbench import mount_feature_workbench
from .workspace import Workspace


def create_app(workspace: Path | None = None) -> FastAPI:
    app = FastAPI(
        title="SRIC Local API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1", "http://localhost"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-Sentinel-Console-Token",
        ],
    )

    @app.middleware("http")
    async def security_headers(request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        if request.url.path.startswith(("/console", "/workbench")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "connect-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/workbench")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    if workspace is not None:
        graph = TemporalGraph(workspace)
        jobs = JobEngine(workspace)
        notebook = ResearchNotebook(workspace)

        @app.get("/graph")
        async def graph_snapshot() -> dict[str, list[dict[str, Any]]]:
            return graph.snapshot()

        @app.get("/graph/query")
        async def graph_query(q: str) -> dict[str, Any]:
            return SecurityResearchGraphQuery(graph).execute(q)

        @app.get("/graph/explain/{object_id}")
        async def graph_explain(object_id: str) -> dict[str, Any]:
            return graph.explain(object_id)

        @app.get("/graph/path")
        async def graph_path(source: str, target: str, max_depth: int = 8) -> dict[str, Any]:
            return graph.path(source, target, max_depth=max_depth)

        @app.get("/workspace/integrity")
        async def workspace_integrity() -> dict[str, object]:
            return Workspace.open(workspace).integrity()

        @app.get("/jobs/dag")
        async def jobs_dag() -> dict[str, Any]:
            return jobs.dag()

        @app.get("/search")
        async def search(q: str, limit: int = 50) -> list[dict[str, Any]]:
            return graph.search(q, max(1, min(limit, 500)))

        @app.get("/jobs")
        async def list_jobs() -> list[dict[str, Any]]:
            return [x.model_dump(mode="json") for x in jobs.list()]

        @app.get("/jobs/events")
        async def job_events(cursor: int = 0, once: bool = False) -> StreamingResponse:
            async def stream() -> Any:
                current = max(0, cursor)
                while True:
                    events = jobs.all_events(current)
                    for event in events:
                        payload = json.dumps(event.model_dump(mode="json"), default=str)
                        yield f"id: {current}\nevent: job\ndata: {payload}\n\n"
                        current += 1
                    if once:
                        if not events:
                            yield "event: heartbeat\ndata: {}\n\n"
                        break
                    await asyncio.sleep(1.0)

            return StreamingResponse(
                stream(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            )

        @app.get("/notebook")
        async def list_notebook() -> list[dict[str, Any]]:
            return [x.model_dump(mode="json") for x in notebook.list()]

    console_config = WebConsoleConfig(
        product="sric-core",
        display_name="SRIC Core",
        cli_module="sric.cli_all",
        version=__version__,
    )
    console_manager = mount_web_console(app, console_config)
    mount_feature_workbench(app, console_config, console_manager)

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Any, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"error": str(exc)})

    return app
