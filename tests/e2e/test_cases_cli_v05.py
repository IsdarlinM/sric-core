import json
from pathlib import Path

from typer.testing import CliRunner

from sric.cli_vnext import app

runner = CliRunner()


def test_case_inspect_and_fingerprint_cli(tmp_path: Path) -> None:
    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(
            {
                "case_id": "case-1",
                "title": "Example",
                "artifacts": [
                    {
                        "artifact_id": "a1",
                        "artifact_type": "HYPOTHESIS",
                        "source_tool": "trustboundary",
                        "source_ref": "candidate:1",
                        "status": "HYPOTHESIS",
                        "evidence_ids": ["ev-1"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inspected = runner.invoke(app, ["case", "inspect", str(case_path), "--required-evidence", "ev-1"])
    assert inspected.exit_code == 0
    assert '"evidence_adequacy": 1.0' in inspected.stdout

    fingerprint = runner.invoke(
        app,
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
            "resource-1",
        ],
    )
    assert fingerprint.exit_code == 0
    assert fingerprint.stdout.strip().startswith("claim:")
