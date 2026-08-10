from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import click
from typer.main import get_command
from typer.testing import CliRunner

import sric.cli_update as cli_update
from sric.cli_all import app
from sric.graph import GraphEdge, GraphNode, TemporalGraph


runner = CliRunner()

EXPECTED_LEAF_COMMANDS = {
    "ai status",
    "ai test",
    "capabilities",
    "case fingerprint",
    "case inspect",
    "claim-transition",
    "doctor",
    "eval list",
    "eval report",
    "eval run",
    "graph diff",
    "graph explain",
    "graph history",
    "graph neighbors",
    "graph path",
    "graph query",
    "help",
    "import-check",
    "job",
    "lineage",
    "notebook",
    "plugins disable",
    "plugins enable",
    "plugins inspect",
    "plugins install",
    "plugins list",
    "plugins remove",
    "plugins verify",
    "query",
    "scope check",
    "secret list",
    "update",
    "version",
    "web",
    "workspace backup",
    "workspace create",
    "workspace integrity",
    "workspace list",
    "workspace migrate",
}


def _leaf_paths(command: click.Command, prefix: tuple[str, ...] = ()) -> set[str]:
    if not isinstance(command, click.Group):
        return {" ".join(prefix)}
    leaves: set[str] = set()
    for name, child in command.commands.items():
        leaves.update(_leaf_paths(child, (*prefix, name)))
    return leaves


def _invoke(args: list[str], expected: int = 0) -> str:
    result = runner.invoke(app, args)
    assert result.exit_code == expected, f"{' '.join(args)} => {result.exit_code}\n{result.output}\n{result.exception}"
    assert "Traceback" not in result.output, f"{' '.join(args)} emitted a traceback"
    return result.output


def test_every_public_sric_command_has_a_deterministic_functional_smoke(tmp_path: Path, monkeypatch) -> None:
    registered = _leaf_paths(get_command(app))
    assert registered == EXPECTED_LEAF_COMMANDS, (
        "Public SRIC CLI changed without functional smoke coverage. "
        f"missing_tests={sorted(registered - EXPECTED_LEAF_COMMANDS)} "
        f"stale_tests={sorted(EXPECTED_LEAF_COMMANDS - registered)}"
    )

    workspace_root = tmp_path / "workspaces"
    workspace_name = "smoke"
    workspace = workspace_root / workspace_name
    plugin_dir = tmp_path / "plugins"

    _invoke(["version"])
    _invoke(["doctor", "--json"])
    _invoke(["capabilities"])
    _invoke(["help"])

    _invoke(["workspace", "create", workspace_name, "--root", str(workspace_root)])
    _invoke(["workspace", "list", "--root", str(workspace_root)])
    _invoke(["workspace", "integrity", str(workspace)])
    _invoke(["workspace", "migrate", str(workspace)])
    backup = tmp_path / "workspace-backup.zip"
    _invoke(["workspace", "backup", str(workspace), "--output", str(backup)])
    assert backup.exists()

    _invoke(["ai", "status"])
    _invoke(["ai", "test"])
    _invoke(["scope", "check", "https://example.test/", "--allow", "example.test"])

    manifest = tmp_path / "plugin.json"
    manifest.write_text(
        json.dumps(
            {
                "name": "smoke-plugin",
                "version": "1.0.0",
                "api_version": "2",
                "type": "analyzer",
                "permissions": ["workspace_access"],
                "capabilities": ["offline-smoke"],
                "entrypoint": "example:Plugin",
            }
        ),
        encoding="utf-8",
    )
    _invoke(["plugins", "list", "--path", str(plugin_dir)])
    _invoke(["plugins", "install", str(manifest), "--path", str(plugin_dir)])
    _invoke(["plugins", "inspect", "smoke-plugin", "--path", str(plugin_dir)])
    _invoke(["plugins", "verify", "smoke-plugin", "--path", str(plugin_dir)])
    _invoke(["plugins", "disable", "smoke-plugin", "--path", str(plugin_dir)])
    _invoke(["plugins", "enable", "smoke-plugin", "--path", str(plugin_dir)])

    graph = TemporalGraph(workspace)
    graph.upsert_node(GraphNode(node_id="actor-a", node_type="actor", label="Actor A", source="smoke"))
    graph.upsert_node(GraphNode(node_id="resource-r", node_type="resource", label="Resource", source="smoke"))
    graph.upsert_edge(
        GraphEdge(
            edge_id="edge-read",
            source_node_id="actor-a",
            target_node_id="resource-r",
            edge_type="can_read",
            discovery_method="smoke",
        )
    )

    _invoke(["query", "Actor", "--workspace", str(workspace)])
    _invoke(
        [
            "graph",
            "query",
            'MATCH actor LABEL "Actor A" EDGE can_read TO resource',
            "--workspace",
            str(workspace),
        ]
    )
    _invoke(["graph", "explain", "actor-a", "--workspace", str(workspace)])
    _invoke(["graph", "neighbors", "actor-a", "--workspace", str(workspace)])
    _invoke(["graph", "path", "actor-a", "resource-r", "--workspace", str(workspace)])
    _invoke(["graph", "history", "actor-a", "--workspace", str(workspace)])
    _invoke(
        [
            "graph",
            "diff",
            "2025-01-01T00:00:00+00:00",
            "2027-01-01T00:00:00+00:00",
            "--workspace",
            str(workspace),
        ]
    )

    _invoke(["job", "--workspace", str(workspace)])
    _invoke(["notebook", "--workspace", str(workspace)])
    _invoke(["notebook", "--workspace", str(workspace), "--type", "note", "--title", "smoke", "--body", "offline"])
    _invoke(["secret", "list", "--workspace", str(workspace)])

    local_file = tmp_path / "safe.txt"
    local_file.write_text("bounded local import", encoding="utf-8")
    _invoke(["import-check", str(local_file)])

    # Lineage has a deterministic, controlled not-found path on an otherwise valid workspace.
    _invoke(["lineage", "unknown-artifact", "--workspace", str(workspace)], expected=2)

    _invoke(["eval", "list"])
    _invoke(["eval", "run"])
    _invoke(["eval", "report"])

    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(
            {
                "case_id": "case-smoke",
                "title": "CLI smoke",
                "artifacts": [
                    {
                        "artifact_id": "artifact-1",
                        "artifact_type": "HYPOTHESIS",
                        "source_tool": "sric-core",
                        "source_ref": "smoke:1",
                        "status": "HYPOTHESIS",
                        "evidence_ids": ["ev-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _invoke(["case", "inspect", str(case_path), "--required-evidence", "ev-1"])
    _invoke(
        [
            "case",
            "fingerprint",
            "--type",
            "authorization",
            "--subject",
            "actor-a",
            "--predicate",
            "read",
            "--object",
            "resource-r",
        ]
    )

    claim_path = tmp_path / "claim.json"
    claim_path.write_text(
        json.dumps(
            {
                "claim_id": "claim-smoke",
                "claim_type": "authorization",
                "statement": "Actor may read resource",
                "status": "HYPOTHESIS",
                "confidence": {"score": 0.4},
                "validation_requirements": ["deterministic check"],
                "source": "cli-smoke",
            }
        ),
        encoding="utf-8",
    )
    _invoke(["claim-transition", str(claim_path), "REJECTED", "--reason", "counterevidence", "--evidence", "ev-counter"])

    monkeypatch.setattr(
        cli_update,
        "perform_product_update",
        lambda **_kwargs: SimpleNamespace(
            current_version="0.5.14",
            available_version="0.5.14",
            update_available=False,
            same_version=True,
            forced=False,
            installed=False,
            product="sric-core",
            artifact="fixture",
            channel="test",
        ),
    )
    _invoke(["update", "--check"])

    web_calls: list[tuple[str, int]] = []

    def fake_uvicorn_run(_app: object, *, host: str, port: int) -> None:
        web_calls.append((host, port))

    monkeypatch.setattr("uvicorn.run", fake_uvicorn_run)
    _invoke(["web", "--host", "127.0.0.1", "--port", "18765"])
    assert web_calls == [("127.0.0.1", 18765)]

    _invoke(["plugins", "remove", "smoke-plugin", "--path", str(plugin_dir)])
