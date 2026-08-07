#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build" / "release-evidence"


def run(name: str, command: list[str]) -> dict[str, object]:
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=ROOT,
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


def require(modules: list[str]) -> None:
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit("Missing release tools: " + ", ".join(missing))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata() -> tuple[str, str, list[str]]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    return project["name"], project["version"], sorted((project.get("scripts") or {}).keys())


def isolated_wheel_smoke(
    wheel: Path, scripts: list[str], offline: bool
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="sentinel-forge-") as temporary:
        venv = Path(temporary) / "venv"
        results.append(
            run("create isolated environment", [sys.executable, "-m", "venv", str(venv)])
        )
        if results[-1]["status"] == "FAIL":
            return results
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = [str(python), "-m", "pip", "install"]
        if offline:
            command.append("--no-deps")
        command.append(str(wheel))
        results.append(run("install built wheel", command))
        if results[-1]["status"] == "FAIL":
            return results
        binary_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        for script in scripts:
            executable = binary_dir / (f"{script}.exe" if os.name == "nt" else script)
            results.append(run(f"{script} --help", [str(executable), "--help"]))
            results.append(run(f"{script} -h", [str(executable), "-h"]))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Local release gate for Sentinel Forge repositories."
    )
    parser.add_argument(
        "--quick", action="store_true", help="Skip audit, build, SBOM and wheel smoke."
    )
    parser.add_argument(
        "--offline", action="store_true", help="Use --no-deps for isolated wheel installation."
    )
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")

    project, version, scripts = metadata()
    require(["pytest", "ruff", "mypy"])
    checks: list[dict[str, object]] = []
    if shutil.which("git") and (ROOT / ".git").exists():
        checks.append(run("git diff --check", ["git", "diff", "--check"]))
    checks.extend(
        [
            run("compileall", [sys.executable, "-m", "compileall", "-q", "src", "tests"]),
            run("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"]),
            run("mypy", [sys.executable, "-m", "mypy", "--strict", "src"]),
            run("pytest", [sys.executable, "-m", "pytest", "-q"]),
        ]
    )
    for name, path in (
        ("security scan", ROOT / "scripts" / "security-scan.py"),
        ("safety evaluations", ROOT / "scripts" / "run-evals.py"),
    ):
        if path.exists():
            checks.append(run(name, [sys.executable, str(path)]))

    artifacts: list[dict[str, object]] = []
    if not args.quick:
        require(["pip_audit", "build"])
        checks.append(run("dependency audit", [sys.executable, "-m", "pip_audit"]))
        OUT.mkdir(parents=True, exist_ok=True)
        sbom = ROOT / "scripts" / "generate-sbom.py"
        if sbom.exists():
            checks.append(
                run(
                    "generate SBOM",
                    [sys.executable, str(sbom), "--output", str(OUT / "sbom.cdx.json")],
                )
            )
        if (ROOT / "dist").exists():
            shutil.rmtree(ROOT / "dist")
        checks.append(run("build", [sys.executable, "-m", "build"]))
        wheels = sorted((ROOT / "dist").glob("*.whl"))
        if wheels:
            checks.extend(isolated_wheel_smoke(wheels[-1], scripts, args.offline))
        else:
            checks.append(
                {
                    "name": "wheel produced",
                    "command": [],
                    "status": "FAIL",
                    "returncode": 1,
                    "duration_seconds": 0.0,
                    "output_tail": "No wheel produced",
                }
            )
        for path in sorted([*(ROOT / "dist").glob("*"), OUT / "sbom.cdx.json"]):
            if path.is_file():
                artifacts.append(
                    {
                        "path": str(path.relative_to(ROOT)),
                        "size": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )

    OUT.mkdir(parents=True, exist_ok=True)
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    report = {
        "schema": "sentinel-forge.local-release-gate.v1",
        "project": project,
        "version": version,
        "python": sys.version,
        "platform": sys.platform,
        "status": status,
        "checks": checks,
        "artifacts": artifacts,
    }
    report_path = OUT / "release-gate.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for item in checks:
        print(f"[{item['status']}] {item['name']}")
        if item["status"] == "FAIL" and item["output_tail"]:
            print(item["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
