#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
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
        if (
            compact.lower() == prefix
            or compact.lower().startswith(prefix + ">")
            or compact.lower().startswith(prefix + "<")
            or compact.lower().startswith(prefix + "=")
        ):
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


def file_sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def build_internal_wheelhouse(root: Path, wheelhouse: Path) -> list[dict[str, Any]]:
    """Build all six candidate wheels before isolated installation tests.

    This allows package smoke tests to resolve unreleased internal 0.5 dependencies from
    exact local artifacts instead of requiring an external package publication first.
    """

    if wheelhouse.exists():
        shutil.rmtree(wheelhouse)
    wheelhouse.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for name in REPOSITORIES:
        repository = root / name
        started = time.monotonic()
        process = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse)],
            cwd=repository,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        results.append(
            {
                "repository": name,
                "status": "PASS" if process.returncode == 0 else "FAIL",
                "returncode": process.returncode,
                "duration_seconds": round(time.monotonic() - started, 3),
                "output_tail": "\n".join((process.stdout or "").splitlines()[-80:]),
            }
        )
        if process.returncode != 0:
            break
    return results


def wheelhouse_manifest(wheelhouse: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": path.name,
            "size": path.stat().st_size,
            "sha256": file_sha256(path),
        }
        for path in sorted(wheelhouse.glob("*.whl"))
    ]


def run_gate(
    repository: Path,
    *,
    quick: bool,
    offline: bool,
    wheelhouse: Path | None,
) -> dict[str, Any]:
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
    env = os.environ.copy()
    if wheelhouse is not None:
        env["SENTINEL_FORGE_WHEELHOUSE"] = str(wheelhouse)
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=repository,
        env=env,
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


def run_ecosystem_smoke(root: Path, selected: tuple[str, ...]) -> dict[str, Any]:
    if set(selected) != set(REPOSITORIES):
        return {
            "status": "SKIP",
            "reason": "cross-product smoke requires all six repositories",
        }
    script = root / "sric-core" / "scripts" / "ecosystem-smoke.py"
    if not script.is_file():
        return {"status": "FAIL", "reason": f"missing {script}"}

    source_paths = [str(root / name / "src") for name in REPOSITORIES]
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(source_paths + ([existing] if existing else []))
    started = time.monotonic()
    process = subprocess.run(
        [sys.executable, str(script)],
        cwd=root / "sric-core",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "status": "PASS" if process.returncode == 0 else "FAIL",
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": "\n".join((process.stdout or "").splitlines()[-80:]),
    }


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
    output = args.root / "sric-core" / "build" / "release-evidence"
    output.mkdir(parents=True, exist_ok=True)
    wheelhouse = output / "wheelhouse"
    wheelhouse_builds: list[dict[str, Any]] = []
    active_wheelhouse: Path | None = None
    if not args.quick and set(selected) == set(REPOSITORIES):
        wheelhouse_builds = build_internal_wheelhouse(args.root, wheelhouse)
        if wheelhouse_builds and all(item["status"] == "PASS" for item in wheelhouse_builds):
            active_wheelhouse = wheelhouse

    gate_results = [
        run_gate(
            args.root / name,
            quick=args.quick,
            offline=args.offline,
            wheelhouse=active_wheelhouse,
        )
        for name in selected
    ]
    ecosystem_smoke = run_ecosystem_smoke(args.root, selected)

    status = "PASS"
    if any(item["status"] != "PASS" for item in compatibility + gate_results):
        status = "FAIL"
    if wheelhouse_builds and any(item["status"] != "PASS" for item in wheelhouse_builds):
        status = "FAIL"
    if ecosystem_smoke["status"] == "FAIL":
        status = "FAIL"

    report_path = output / "ecosystem-release-gate.json"
    report = {
        "schema": "sentinel-forge.ecosystem-release-gate.v3",
        "status": status,
        "repository_order": list(selected),
        "versions": {name: data["version"] for name, data in metadata.items()},
        "compatibility": compatibility,
        "wheelhouse_builds": wheelhouse_builds,
        "wheelhouse_artifacts": wheelhouse_manifest(wheelhouse) if wheelhouse.exists() else [],
        "repositories": gate_results,
        "ecosystem_smoke": ecosystem_smoke,
    }
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    for item in compatibility:
        print(
            f"[{item['status']}] {item['repository']} -> {item['dependency']} "
            f"{item['declared_spec']} (current {item['installed_version']})"
        )
    for item in wheelhouse_builds:
        print(f"[{item['status']}] build candidate wheel: {item['repository']}")
        if item["status"] != "PASS" and item.get("output_tail"):
            print(item["output_tail"])
    for item in gate_results:
        print(f"[{item['status']}] {item['repository']}")
        if item["status"] != "PASS" and item.get("output_tail"):
            print(item["output_tail"])
    print(f"[{ecosystem_smoke['status']}] ecosystem contract smoke")
    if ecosystem_smoke.get("output_tail"):
        print(ecosystem_smoke["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
