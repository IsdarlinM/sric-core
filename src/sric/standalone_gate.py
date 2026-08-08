from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from typing import Any, cast

SIBLING_PRODUCTS = {"reprosec", "authtwin", "fossilscope", "trustboundary", "exposuredna"}


def _run(name: str, command: list[str], *, cwd: Path) -> dict[str, Any]:
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return {
        "name": name,
        "command": command,
        "status": "PASS" if process.returncode == 0 else "FAIL",
        "returncode": process.returncode,
        "duration_seconds": round(time.monotonic() - started, 3),
        "output_tail": "\n".join((process.stdout or "").splitlines()[-80:]),
    }


def _dependency_name(value: str) -> str:
    return re.split(r"[<>=!~;\[ ]", value.strip().lower(), maxsplit=1)[0]


def _source_identity(root: Path) -> dict[str, object]:
    identity: dict[str, object] = {"commit_sha": None, "tree_sha": None, "dirty": None}
    if not shutil.which("git") or not (root / ".git").exists():
        identity["note"] = "Git metadata unavailable."
        return identity

    def capture(*args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        ).stdout.strip()

    try:
        identity["commit_sha"] = capture("rev-parse", "HEAD")
        identity["tree_sha"] = capture("rev-parse", "HEAD^{tree}")
        identity["dirty"] = bool(capture("status", "--porcelain"))
    except (OSError, subprocess.CalledProcessError) as exc:
        identity["note"] = f"Unable to resolve Git identity: {exc}"
    return identity


def main() -> int:
    parser = argparse.ArgumentParser(description="Sentinel Forge Standalone Product Contract gate")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = cast(Path, args.root).resolve()
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = cast(dict[str, Any], document["project"])
    project_name = cast(str, project["name"])
    project_version = cast(str, project["version"])
    scripts = cast(dict[str, str], project.get("scripts", {}))
    if len(scripts) != 1:
        raise SystemExit("Standalone gate currently requires exactly one public console script")
    command_name = next(iter(scripts))

    declared_dependencies = cast(list[str], project.get("dependencies", []))
    runtime_dependencies = [_dependency_name(item) for item in declared_dependencies]
    forbidden = sorted(
        name for name in SIBLING_PRODUCTS if name != project_name and name in runtime_dependencies
    )
    dependency_check: dict[str, Any] = {
        "name": "no mandatory sibling product dependencies",
        "command": [],
        "status": "PASS" if not forbidden else "FAIL",
        "returncode": 0 if not forbidden else 1,
        "duration_seconds": 0.0,
        "output_tail": "" if not forbidden else "Mandatory sibling dependencies: " + ", ".join(forbidden),
    }
    if project_name != "sric-core" and "sric-core" not in runtime_dependencies:
        dependency_check["status"] = "FAIL"
        dependency_check["returncode"] = 1
        dependency_check["output_tail"] = "Product must depend directly on sric-core."

    checks: list[dict[str, Any]] = [dependency_check]
    standalone_tests = root / "tests" / "standalone"
    if standalone_tests.is_dir():
        checks.append(
            _run(
                "standalone pytest",
                [sys.executable, "-m", "pytest", str(standalone_tests), "-q"],
                cwd=root,
            )
        )
    else:
        checks.append(
            {
                "name": "standalone pytest",
                "command": [],
                "status": "FAIL",
                "returncode": 1,
                "duration_seconds": 0.0,
                "output_tail": "tests/standalone is required",
            }
        )

    executable = shutil.which(command_name)
    if executable is None:
        checks.append(
            {
                "name": "installed console script",
                "command": [command_name],
                "status": "FAIL",
                "returncode": 1,
                "duration_seconds": 0.0,
                "output_tail": f"{command_name} is not installed on PATH",
            }
        )
    else:
        for name, argv in (
            ("root --help", [executable, "--help"]),
            ("root -h", [executable, "-h"]),
            ("root help", [executable, "help"]),
            ("version", [executable, "version"]),
            ("doctor", [executable, "doctor"]),
            ("capabilities", [executable, "capabilities"]),
        ):
            checks.append(_run(name, argv, cwd=root))

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    output = root / "build" / "release-evidence"
    output.mkdir(parents=True, exist_ok=True)
    report_path = output / "standalone-gate.json"
    report: dict[str, Any] = {
        "schema": "sentinel-forge.standalone-product-contract.v1",
        "project": project_name,
        "version": project_version,
        "source": _source_identity(root),
        "status": status,
        "checks": checks,
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for item in checks:
        print(f"[{item['status']}] {item['name']}")
        if item["status"] == "FAIL" and item["output_tail"]:
            print(item["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
