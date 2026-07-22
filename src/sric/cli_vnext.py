from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from . import cli as base
from .claims import ClaimContract, transition_claim
from .evals import BUILTIN_CASES, EvalRunner
from .graph import TemporalGraph
from .models import ClaimStatus
from .query import GraphQueryError, SecurityResearchGraphQuery
from .vault import SecretVault
from .workspace import Workspace

app=base.app
workspace_app=base.workspace_app
graph_app=typer.Typer(context_settings={"help_option_names":["-h","--help"]},help="Inspect/query the shared temporal security graph.")
eval_app=typer.Typer(context_settings={"help_option_names":["-h","--help"]},help="Run versioned AI/safety evaluation suites.")
secret_app=typer.Typer(context_settings={"help_option_names":["-h","--help"]},help="Manage opaque secret references without logging secret values.")
app.add_typer(graph_app,name="graph"); app.add_typer(eval_app,name="eval"); app.add_typer(secret_app,name="secret")

@workspace_app.command("integrity")
def workspace_integrity(path:Path=typer.Argument(...,exists=True,file_okay=False))->None: typer.echo(json.dumps(Workspace.open(path).integrity(),indent=2))
@workspace_app.command("migrate")
def workspace_migrate(path:Path=typer.Argument(...,exists=True,file_okay=False))->None:
    ws=Workspace(path.resolve()); typer.echo(json.dumps({"changes":ws.migrate(),"integrity":ws.integrity()},indent=2))
@workspace_app.command("backup")
def workspace_backup(path:Path=typer.Argument(...,exists=True,file_okay=False),output:Optional[Path]=typer.Option(None,"--output"))->None: typer.echo(str(Workspace.open(path).backup(output)))

@graph_app.command("query")
def graph_query(expression:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False),explain:bool=typer.Option(False,"--explain"))->None:
    q=SecurityResearchGraphQuery(TemporalGraph(workspace))
    try: payload=q.explain_plan(expression) if explain else q.execute(expression)
    except GraphQueryError as exc: typer.echo(f"Invalid graph query: {exc}",err=True); raise typer.Exit(2)
    typer.echo(json.dumps(payload,indent=2,default=str))
@graph_app.command("explain")
def graph_explain(object_id:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False))->None:
    try: payload=TemporalGraph(workspace).explain(object_id)
    except KeyError: typer.echo(f"Unknown graph object: {object_id}",err=True); raise typer.Exit(2)
    typer.echo(json.dumps(payload,indent=2,default=str))
@graph_app.command("neighbors")
def graph_neighbors(node_id:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False))->None: typer.echo(json.dumps(TemporalGraph(workspace).neighbors(node_id),indent=2,default=str))
@graph_app.command("path")
def graph_path(source:str,target:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False),max_depth:int=typer.Option(8,"--max-depth"))->None: typer.echo(json.dumps(TemporalGraph(workspace).path(source,target,max_depth=max_depth),indent=2))
@graph_app.command("history")
def graph_history(object_id:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False))->None: typer.echo(json.dumps(TemporalGraph(workspace).history(object_id),indent=2,default=str))
@graph_app.command("diff")
def graph_diff(before:str,after:str,workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False))->None:
    from datetime import datetime
    try: a=datetime.fromisoformat(before.replace("Z","+00:00")); b=datetime.fromisoformat(after.replace("Z","+00:00"))
    except ValueError: typer.echo("before/after must be ISO-8601",err=True); raise typer.Exit(2)
    typer.echo(json.dumps(TemporalGraph(workspace).diff(a,b),indent=2,default=str))

@eval_app.command("list")
def eval_list()->None: typer.echo(json.dumps([x.__dict__ for x in BUILTIN_CASES],indent=2))
@eval_app.command("run")
def eval_run(category:Optional[str]=typer.Option(None,"--category"))->None:
    results=EvalRunner().run(category); passed=sum(bool(x["passed"]) for x in results); typer.echo(json.dumps({"passed":passed,"total":len(results),"results":results},indent=2));
    if passed!=len(results): raise typer.Exit(1)
@eval_app.command("report")
def eval_report(category:Optional[str]=typer.Option(None,"--category"))->None: typer.echo(json.dumps({"suite_version":"1","principle":"AI proposes. Evidence proves. Humans control.","results":EvalRunner().run(category)},indent=2))
@secret_app.command("list")
def secret_list(workspace:Path=typer.Option(...,"--workspace",exists=True,file_okay=False))->None: typer.echo(json.dumps([x.__dict__ for x in SecretVault(workspace).list()],indent=2))
@app.command("claim-transition")
def claim_transition(path:Path=typer.Argument(...,exists=True,dir_okay=False),status:ClaimStatus=typer.Argument(...),reason:str=typer.Option(...,"--reason"),evidence:list[str]=typer.Option([],"--evidence"),deterministic:bool=typer.Option(False,"--deterministic"))->None:
    claim=ClaimContract.model_validate_json(path.read_text(encoding="utf-8"))
    try: updated=transition_claim(claim,status,reason=reason,evidence_ids=evidence,deterministic=deterministic)
    except ValueError as exc: typer.echo(str(exc),err=True); raise typer.Exit(2)
    path.write_text(updated.model_dump_json(indent=2),encoding="utf-8"); typer.echo(updated.model_dump_json(indent=2))

def run()->None: base.run()
