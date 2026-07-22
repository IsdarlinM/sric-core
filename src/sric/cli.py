from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Optional

import typer

from . import __version__
from .ai import AIRequest, AIService
from .api import create_app
from .query import GraphQueryError, SecurityResearchGraphQuery
from .plugins import PluginRegistry
from .graph import TemporalGraph
from .jobs import JobEngine
from .lineage import EvidenceLineage
from .notebook import ResearchNotebook, NotebookEntry
from .imports import SafeImportPipeline
from .scope import ScopeEngine, ScopePolicy
from .workspace import Workspace
from .updater import perform_update

app = typer.Typer(
    name="sric",
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Security Research Intelligence Core — evidence-native shared primitives.",
    no_args_is_help=True,
    add_completion=True,
    rich_markup_mode=None,
)
workspace_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Create and inspect isolated research workspaces.",
)
plugins_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Inspect plugin manifests and declared permissions.",
)
ai_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Inspect AI mode. AI is disabled by default.",
)
scope_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Evaluate targets against explicit scope policy.",
)
app.add_typer(workspace_app, name="workspace")
app.add_typer(plugins_app, name="plugins")
app.add_typer(ai_app, name="ai")
app.add_typer(scope_app, name="scope")


def _home() -> Path:
    return Path.home() / ".sric"


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """SRIC Core CLI. Use `sric COMMAND --help` for command-specific help."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("version")
def version() -> None:
    """Print the installed SRIC version."""
    typer.echo(__version__)


@app.command("doctor")
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Check Python/runtime prerequisites and local configuration."""
    import sys

    checks: dict[str, dict[str, object]] = {
        "python": {"ok": sys.version_info >= (3, 11), "version": sys.version.split()[0]},
        "home_writable": {"ok": _home().parent.exists() and _home().parent.is_dir()},
        "loopback_dns": {"ok": socket.gethostbyname("localhost").startswith("127.")},
        "ai_default": {"ok": True, "mode": "disabled"},
    }
    ok = all(bool(v["ok"]) for v in checks.values())
    payload = {"ok": ok, "checks": checks}
    if json_output:
        typer.echo(json.dumps(payload, indent=2))
    else:
        for name, item in checks.items():
            typer.echo(f"[{'OK' if item['ok'] else 'FAIL'}] {name}: {item}")
    if not ok:
        raise typer.Exit(1)


@workspace_app.command("create")
def workspace_create(
    name: str, root: Path = typer.Option(_home() / "workspaces", "--root")
) -> None:
    """Create an isolated workspace with its own database and evidence store."""
    root.mkdir(parents=True, exist_ok=True)
    ws = Workspace.create(root, name)
    typer.echo(str(ws.root))


@workspace_app.command("list")
def workspace_list(root: Path = typer.Option(_home() / "workspaces", "--root")) -> None:
    """List local workspaces."""
    if not root.exists():
        return
    for p in sorted(root.iterdir()):
        if (p / "workspace.json").is_file():
            typer.echo(p.name)


@plugins_app.command("list")
def plugins_list(path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """List installed plugin manifests. Plugin code is not auto-executed."""
    for manifest in PluginRegistry(path).list():
        typer.echo(f"{manifest.name}\t{manifest.version}\t{manifest.type}")


@plugins_app.command("inspect")
def plugins_inspect(name: str, path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """Show a plugin manifest and declared permissions."""
    try:
        manifest = PluginRegistry(path).inspect(name)
    except KeyError:
        typer.echo(f"Plugin not found: {name}", err=True)
        raise typer.Exit(2)
    typer.echo(manifest.model_dump_json(indent=2))


@ai_app.command("status")
def ai_status() -> None:
    """Show the default AI mode. Cloud AI is never enabled implicitly."""
    typer.echo(
        json.dumps({"mode": "disabled", "provider": "disabled", "cloud_uploads": False}, indent=2)
    )


@ai_app.command("test")
def ai_test() -> None:
    """Verify that disabled mode fails closed rather than making an external call."""
    try:
        AIService().complete(AIRequest(capability="test", sanitized_payload="test"))
    except RuntimeError as exc:
        typer.echo(str(exc))
        return
    raise typer.Exit(1)


@scope_app.command("check")
def scope_check(
    target: str,
    method: str = typer.Option("GET", "--method"),
    allow: list[str] = typer.Option([], "--allow"),
    deny: list[str] = typer.Option([], "--deny"),
) -> None:
    """Evaluate a target against an explicit allow/deny scope policy."""
    decision = ScopeEngine(ScopePolicy(allow_targets=allow, deny_targets=deny)).evaluate(
        target, method
    )
    from dataclasses import asdict

    typer.echo(json.dumps(asdict(decision), indent=2))
    if not decision.allowed:
        raise typer.Exit(3)




@plugins_app.command("install")
def plugins_install(
    manifest: Path, path: Path = typer.Option(_home() / "plugins", "--path")
) -> None:
    """Install a validated plugin manifest only; plugin code is never auto-executed."""
    try:
        installed = PluginRegistry(path).install_manifest(manifest)
    except Exception as exc:
        typer.echo(f"Plugin install failed: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(installed.model_dump_json(indent=2))


@plugins_app.command("disable")
def plugins_disable(name: str, path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """Disable an installed plugin without deleting its manifest."""
    PluginRegistry(path).disable(name)
    typer.echo(f"disabled {name}")


@plugins_app.command("enable")
def plugins_enable(name: str, path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """Enable a previously disabled plugin manifest."""
    PluginRegistry(path).enable(name)
    typer.echo(f"enabled {name}")


@plugins_app.command("verify")
def plugins_verify(name: str, path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """Verify plugin manifest integrity/shape and show declared permissions."""
    typer.echo(json.dumps(PluginRegistry(path).verify(name), indent=2))


@plugins_app.command("remove")
def plugins_remove(name: str, path: Path = typer.Option(_home() / "plugins", "--path")) -> None:
    """Remove an installed plugin manifest."""
    PluginRegistry(path).remove(name)
    typer.echo(f"removed {name}")


@app.command("query")
def query_workspace(
    query: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
    limit: int = typer.Option(50, "--limit", min=1, max=500),
    dsl: bool = typer.Option(False, "--dsl", help="Interpret QUERY as read-only Security Research Graph Query Language."),
) -> None:
    """Search the temporal graph or execute the read-only graph query DSL."""
    graph = TemporalGraph(workspace)
    if dsl:
        try:
            payload = SecurityResearchGraphQuery(graph).execute(query)
        except GraphQueryError as exc:
            typer.echo(f"Invalid graph query: {exc}", err=True)
            raise typer.Exit(2)
    else:
        payload = graph.search(query, limit)
    typer.echo(json.dumps(payload, indent=2, default=str))


@app.command("job")
def job_command(
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
    job_id: Optional[str] = typer.Option(None, "--id"),
    cancel: bool = typer.Option(False, "--cancel"),
) -> None:
    """List jobs, inspect one job, or request cancellation."""
    engine = JobEngine(workspace)
    if job_id and cancel:
        typer.echo(engine.request_cancel(job_id).model_dump_json(indent=2))
    elif job_id:
        payload = {
            "job": engine.get(job_id).model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in engine.events(job_id)],
        }
        typer.echo(json.dumps(payload, indent=2, default=str))
    else:
        typer.echo(json.dumps([j.model_dump(mode="json") for j in engine.list()], indent=2, default=str))


@app.command("notebook")
def notebook_command(
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
    entry_type: Optional[str] = typer.Option(None, "--type"),
    title: Optional[str] = typer.Option(None, "--title"),
    body: Optional[str] = typer.Option(None, "--body"),
    status: str = typer.Option("OBSERVED", "--status"),
    save_query_name: Optional[str] = typer.Option(None, "--save-query-name"),
    query: Optional[str] = typer.Option(None, "--query"),
    list_queries: bool = typer.Option(False, "--list-queries"),
) -> None:
    """List/append research notes or manage saved investigation queries."""
    notebook = ResearchNotebook(workspace)
    if save_query_name or query:
        if not (save_query_name and query):
            typer.echo("--save-query-name and --query are required together", err=True)
            raise typer.Exit(2)
        notebook.save_query(save_query_name, query)
        typer.echo(json.dumps({"saved": save_query_name, "query": query}, indent=2))
        return
    if list_queries:
        typer.echo(json.dumps(notebook.saved_queries(), indent=2))
        return
    if entry_type or title or body:
        if not (entry_type and title and body):
            typer.echo("--type, --title and --body are required together", err=True)
            raise typer.Exit(2)
        entry = notebook.add(NotebookEntry(entry_type=entry_type, title=title, body=body, status=status))
        typer.echo(entry.model_dump_json(indent=2))
        return
    typer.echo(json.dumps([e.model_dump(mode="json") for e in notebook.list()], indent=2, default=str))


@app.command("lineage")
def lineage_command(
    artifact_id: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    """Explain evidence lineage from source observations to a derived artifact."""
    try:
        payload = EvidenceLineage(workspace).explain(artifact_id)
    except KeyError:
        typer.echo(f"Unknown artifact: {artifact_id}", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps(payload, indent=2, default=str))


@app.command("import-check")
def import_check(path: Path = typer.Argument(..., exists=True, dir_okay=False)) -> None:
    """Validate a hostile local import or ZIP before any parser consumes it."""
    pipeline = SafeImportPipeline()
    try:
        payload = pipeline.inspect_zip(path) if path.suffix.lower() in {".zip", ".rcap"} else pipeline.validate_file(path)
    except Exception as exc:
        typer.echo(f"Import rejected: {exc}", err=True)
        raise typer.Exit(2)
    typer.echo(json.dumps({"valid": True, **payload}, indent=2))

@app.command("update")
def update(
    check: bool = typer.Option(
        False, "--check", help="Verify release metadata and only report availability."
    ),
    manifest: Optional[str] = typer.Option(
        None, "--manifest", help="Signed release manifest path or HTTPS URL."
    ),
    public_key: Optional[Path] = typer.Option(
        None, "--public-key", help="Trusted Ed25519 release public key."
    ),
) -> None:
    """Check or install a signed wheel release; never performs a blind git pull."""
    import os

    source = manifest or os.getenv("SRIC_RELEASE_MANIFEST_URL")
    key = public_key or (
        Path(os.environ["SRIC_RELEASE_PUBLIC_KEY"])
        if os.getenv("SRIC_RELEASE_PUBLIC_KEY")
        else None
    )
    if not source or key is None:
        typer.echo(
            "No trusted release channel configured. Provide --manifest and --public-key, "
            "or SRIC_RELEASE_MANIFEST_URL/SRIC_RELEASE_PUBLIC_KEY.",
            err=True,
        )
        raise typer.Exit(2)
    try:
        status = perform_update(
            manifest_source=source,
            public_key_path=key,
            expected_product="sric-core",
            current_version=__version__,
            check_only=check,
        )
    except Exception as exc:
        typer.echo(f"Update verification failed; no update was installed: {exc}", err=True)
        raise typer.Exit(6)
    typer.echo(json.dumps(status.__dict__, indent=2))


@app.command("web")
def web(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port", min=1, max=65535),
) -> None:
    """Run the local SRIC API. Non-loopback binding remains rejected until authenticated TLS mode is configured."""
    if host not in {"127.0.0.1", "localhost", "::1"}:
        typer.echo(
            "Non-loopback binding is disabled until authenticated TLS mode is configured.",
            err=True,
        )
        raise typer.Exit(4)
    import uvicorn

    uvicorn.run(create_app(), host=host, port=port)


@app.command("help", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def help_command(ctx: typer.Context, command: Optional[str] = typer.Argument(None)) -> None:
    """Show root help or help for a top-level command."""
    if not command:
        typer.echo(ctx.parent.get_help() if ctx.parent else ctx.get_help())
        return
    root = ctx.parent.command if ctx.parent else app
    if hasattr(root, "commands") and command in root.commands:
        typer.echo(root.commands[command].get_help(ctx))
        return
    typer.echo(f"Unknown command: {command}", err=True)
    raise typer.Exit(2)


def run() -> None:
    """Console entrypoint with support for `sric COMMAND help`."""
    import sys

    if len(sys.argv) >= 3 and sys.argv[-1] == "help" and sys.argv[1] != "help":
        sys.argv[-1] = "--help"
    app()
