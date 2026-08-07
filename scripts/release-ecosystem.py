#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import tomllib
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


def project_metadata(repository: Path) -> dict[str, Any]:
    path = repository / "pyproject.toml"
    if not path.exists():
        raise FileNotFoundError(f"missing {path}")
    project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
    return {
        "name": project["name"],
        "version": project["version"],
        "dependencies": list(project.get("dependencies", [])),
        "optional_dependencies": dict(project.get("optional-dependencies", {})),
    }


def dependency_spec(metadata: dict[str, Any], package: str) -> str | None:
    prefix = package.lower()
    for dependency in metadata["dependencies"]:
        compact = dependency.replace(" ", "")
        if compact.lower() == prefix or compact.lower().startswith(prefix + ">") or compact.lower().startswith(prefix + "<") or compact.lower().startswith(prefix + "="):
            return compact[len(package) :]
    return None


def version_tuple(value: str) -> tuple[int, int, int]:
    core = value.split("+", 1)[0].split("-", 1)[0]
    parts = core.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError(f"unsupported semantic version: {value}")
    return tuple(int(part) for part in parts)  # type: ignore[return-value]


def compatible(version: str, spec: str | None) -> bool:
    if spec is None:
        return False
    current = version_tuple(version)
    for clause in (part for part in spec.split(",") if part):
        if clause.startswith(">=") and current < version_tuple(clause[2:]):
            return False
        if clause.startswith(">") and current <= version_tuple(clause[1:]):
            return False
        if clause.startswith("<=") and current > version_tuple(clause[2:]):
            return False
        if clause.startswith("<") and current >= version_tuple(clause[1:]):
            return False
        if clause.startswith("==") and current != version_tuple(clause[2:]):
            return False
    return True


def run_gate(repository: Path, *, quick: bool, offline: bool) -> dict[str, Any]:
    script = repository / "scripts" / "release-gate.py"
    if not script.exists():
        return {
            "repository": repository.name,
            "status": "FAIL",
            "reason": "missing scripts/release-gate.py",
        }
    command = [sys.executable, str(script)]
    if quick:
        command.append("--quick")
    if offline:
        command.append("--offline")
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=repository,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    report_path = repository / "build" / "release-evidence" / "release-gate.json"
    report: dict[str, Any] = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            report = {"report_error": str(exc)}
    return {
        "repository": repository.name,
        "status": "PASS" if process.returncode == 0 and report.get("status") == "PASS" else "FAIL",
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": "\n".join((process.stdout or "").splitlines()[-80:]),
        "report_path": str(report_path),
        "report": report,
    }


def compatibility_checks(metadata: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    core_version = metadata["sric-core"]["version"]
    reprosec_version = metadata["reprosec"]["version"]
    for repository in REPOSITORIES[1:]:
        spec = dependency_spec(metadata[repository], "sric-core")
        checks.append(
            {
                "repository": repository,
                "dependency": "sric-core",
                "installed_version": core_version,
                "declared_spec": spec,
                "status": "PASS" if compatible(core_version, spec) else "FAIL",
            }
        )
    rcap_spec = None
    for dependency in metadata["authtwin"]["optional_dependencies"].get("rcap", []):
        compact = dependency.replace(" ", "")
        if compact.lower().startswith("reprosec"):
            rcap_spec = compact[len("reprosec") :]
    checks.append(
        {
            "repository": "authtwin",
            "dependency": "reprosec[rcap]",
            "installed_version": reprosec_version,
            "declared_spec": rcap_spec,
            "status": "PASS" if compatible(reprosec_version, rcap_spec) else "FAIL",
        }
    )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Sentinel Forge local release train")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Directory containing the six sibling repositories",
    )
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--only", action="append", choices=REPOSITORIES)
    args = parser.parse_args()

    selected = tuple(args.only or REPOSITORIES)
    metadata: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for name in REPOSITORIES:
        repository = args.root / name
        try:
            metadata[name] = project_metadata(repository)
        except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError, ValueError) as exc:
            missing.append(f"{name}: {exc}")
    if missing:
        for error in missing:
            print(f"[FAIL] {error}")
        return 1

    compatibility = compatibility_checks(metadata)
    gate_results = [
        run_gate(args.root / name, quick=args.quick, offline=args.offline)
        for name in selected
    ]
    status = "PASS"
    if any(item["status"] != "PASS" for item in compatibility + gate_results):
        status = "FAIL"

    output = args.root / "sric-core" / "build" / "release-evidence"
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "ecosystem-release-gate.json"
    report = {
        "schema": "sentinel-forge.ecosystem-release-gate.v1",
        "status": status,
        "repository_order": list(selected),
        "versions": {name: data["version"] for name, data in metadata.items()},
        "compatibility": compatibility,
        "repositories": gate_results,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    for item in compatibility:
        print(
            f"[{item['status']}] {item['repository']} -> {item['dependency']} "
            f"{item['declared_spec']} (current {item['installed_version']})"
        )
    for item in gate_results:
        print(f"[{item['status']}] {item['repository']}")
        if item["status"] != "PASS" and item.get("output_tail"):
            print(item["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
