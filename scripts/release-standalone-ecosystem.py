#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPOSITORIES = (
    "sric-core",
    "reprosec",
    "authtwin",
    "fossilscope",
    "trustboundary",
    "exposuredna",
)


def run_one(root: Path, name: str) -> dict[str, Any]:
    repository = root / name
    started = time.monotonic()
    process = subprocess.run(
        [sys.executable, "-m", "sric.standalone_gate", "--root", str(repository)],
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    evidence_path = repository / "build" / "release-evidence" / "standalone-gate.json"
    evidence: dict[str, Any] = {}
    if evidence_path.is_file():
        try:
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            evidence = {"read_error": str(exc)}
    return {
        "repository": name,
        "status": "PASS" if process.returncode == 0 and evidence.get("status") == "PASS" else "FAIL",
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": "\n".join((process.stdout or "").splitlines()[-100:]),
        "evidence": evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run standalone conformance for every Sentinel Forge repository")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Directory containing the six sibling repositories.",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    results = [run_one(root, name) for name in REPOSITORIES]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"

    output = root / "sric-core" / "build" / "release-evidence"
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "ecosystem-standalone-gate.json"
    report = {
        "schema": "sentinel-forge.ecosystem-standalone-gate.v1",
        "status": status,
        "repositories": results,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in results:
        print(f"[{item['status']}] {item['repository']}")
        if item["status"] != "PASS":
            print(item["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
