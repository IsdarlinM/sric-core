from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from pydantic import ValidationError

from . import cli as base
from .api_vnext import create_app as create_vnext_app
from .claims import ClaimContract, transition_claim
from .evals import BUILTIN_CASES, EvalRunner
from .graph import TemporalGraph
from .models import ClaimStatus
from .query import GraphQueryError, SecurityResearchGraphQuery
from .vault import SecretVault
from .workspace import Workspace

base.create_app = create_vnext_app

app = base.app
workspace_app = base.workspace_app
graph_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Inspect/query the shared temporal security graph.",
)
eval_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Run versioned AI/safety evaluation suites.",
)
secret_app = typer.Typer(
    context_settings={"help_option_names": ["-h", "--help"]},
    help="Manage opaque secret references without logging secret values.",
)
app.add_typer(graph_app, name="graph")
app.add_typer(eval_app, name="eval")
app.add_typer(secret_app, name="secret")


@workspace_app.command("integrity")
def workspace_integrity(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    typer.echo(json.dumps(Workspace.open(path).integrity(), indent=2))


@workspace_app.command("migrate")
def workspace_migrate(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
) -> None:
    workspace = Workspace(path.resolve())
    typer.echo(
        json.dumps(
            {"changes": workspace.migrate(), "integrity": workspace.integrity()},
            indent=2,
        )
    )


@workspace_app.command("backup")
def workspace_backup(
    path: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Optional[Path] = typer.Option(None, "--output"),
) -> None:
    typer.echo(str(Workspace.open(path).backup(output)))


@graph_app.command("query")
def graph_query(
    expression: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
    explain: bool = typer.Option(False, "--explain"),
) -> None:
    query = SecurityResearchGraphQuery(TemporalGraph(workspace))
    try:
        payload = query.explain_plan(expression) if explain else query.execute(expression)
    except GraphQueryError as exc:
        typer.echo(f"Invalid graph query: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(payload, indent=2, default=str))


@graph_app.command("explain")
def graph_explain(
    object_id: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    try:
        payload = TemporalGraph(workspace).explain(object_id)
    except KeyError as exc:
        typer.echo(f"Unknown graph object: {object_id}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(json.dumps(payload, indent=2, default=str))


@graph_app.command("neighbors")
def graph_neighbors(
    node_id: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    typer.echo(json.dumps(TemporalGraph(workspace).neighbors(node_id), indent=2, default=str))


@graph_app.command("path")
def graph_path(
    source: str,
    target: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
    max_depth: int = typer.Option(8, "--max-depth", min=1, max=64),
) -> None:
    typer.echo(
        json.dumps(
            TemporalGraph(workspace).path(source, target, max_depth=max_depth),
            indent=2,
        )
    )


@graph_app.command("history")
def graph_history(
    object_id: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    typer.echo(json.dumps(TemporalGraph(workspace).history(object_id), indent=2, default=str))


@graph_app.command("diff")
def graph_diff(
    before: str,
    after: str,
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    try:
        before_time = datetime.fromisoformat(before.replace("Z", "+00:00"))
        after_time = datetime.fromisoformat(after.replace("Z", "+00:00"))
    except ValueError as exc:
        typer.echo("before/after must be ISO-8601", err=True)
        raise typer.Exit(2) from exc
    typer.echo(
        json.dumps(
            TemporalGraph(workspace).diff(before_time, after_time),
            indent=2,
            default=str,
        )
    )


@eval_app.command("list")
def eval_list() -> None:
    typer.echo(json.dumps([case.__dict__ for case in BUILTIN_CASES], indent=2))


@eval_app.command("run")
def eval_run(
    category: Optional[str] = typer.Option(None, "--category"),
) -> None:
    results = EvalRunner().run(category)
    passed = sum(bool(item["passed"]) for item in results)
    typer.echo(json.dumps({"passed": passed, "total": len(results), "results": results}, indent=2))
    if passed != len(results):
        raise typer.Exit(1)


@eval_app.command("report")
def eval_report(
    category: Optional[str] = typer.Option(None, "--category"),
) -> None:
    typer.echo(
        json.dumps(
            {
                "suite_version": "1",
                "principle": "AI proposes. Evidence proves. Humans control.",
                "results": EvalRunner().run(category),
            },
            indent=2,
        )
    )


@secret_app.command("list")
def secret_list(
    workspace: Path = typer.Option(..., "--workspace", exists=True, file_okay=False),
) -> None:
    typer.echo(json.dumps([item.__dict__ for item in SecretVault(workspace).list()], indent=2))


@app.command("claim-transition")
def claim_transition(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
    status: ClaimStatus = typer.Argument(...),
    reason: str = typer.Option(..., "--reason"),
    evidence: list[str] = typer.Option([], "--evidence"),
    deterministic: bool = typer.Option(False, "--deterministic"),
) -> None:
    try:
        claim = ClaimContract.model_validate_json(path.read_text(encoding="utf-8"))
        updated = transition_claim(
            claim,
            status,
            reason=reason,
            evidence_ids=evidence,
            deterministic=deterministic,
        )
        path.write_text(updated.model_dump_json(indent=2), encoding="utf-8")
    except (OSError, ValidationError, ValueError) as exc:
        typer.echo(f"claim transition failed: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(updated.model_dump_json(indent=2))


def _normalize_trailing_help(argv: list[str]) -> list[str]:
    normalized = list(argv)
    if len(normalized) >= 3 and normalized[-1] == "help" and normalized[1] != "help":
        normalized[-1] = "--help"
    return normalized


def run() -> None:
    """Console entrypoint supporting `tool COMMAND help` at any command depth."""
    sys.argv[:] = _normalize_trailing_help(sys.argv)
    app()
