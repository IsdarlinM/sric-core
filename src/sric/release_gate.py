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
from typing import Sequence


def _run(
    root: Path,
    name: str,
    command: list[str],
) -> dict[str, object]:
    started = time.monotonic()
    process = subprocess.run(
        command,
        cwd=root,
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


def _require(*modules: str) -> None:
    missing = [name for name in modules if importlib.util.find_spec(name) is None]
    if missing:
        raise SystemExit("Missing release tools: " + ", ".join(missing))


def _digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def _project_metadata(root: Path) -> tuple[str, str, list[str]]:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    return project["name"], project["version"], sorted(project.get("scripts", {}))


def _wheel_smoke(
    root: Path,
    wheel: Path,
    scripts: list[str],
    *,
    offline: bool,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="sentinel-forge-") as directory:
        venv = Path(directory) / "venv"
        venv_command = [sys.executable, "-m", "venv"]
        if offline:
            venv_command.append("--system-site-packages")
        venv_command.append(str(venv))
        results.append(_run(root, "create isolated environment", venv_command))
        if results[-1]["status"] == "FAIL":
            return results
        python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        command = [str(python), "-m", "pip", "install"]
        wheelhouse = os.environ.get("SENTINEL_FORGE_WHEELHOUSE")
        if wheelhouse:
            command.extend(["--find-links", wheelhouse])
        if offline:
            command.append("--no-deps")
        command.append(str(wheel))
        results.append(_run(root, "install built wheel", command))
        if results[-1]["status"] == "FAIL":
            return results
        bin_dir = venv / ("Scripts" if os.name == "nt" else "bin")
        for script in scripts:
            executable = bin_dir / (f"{script}.exe" if os.name == "nt" else script)
            results.append(_run(root, f"{script} --help", [str(executable), "--help"]))
            results.append(_run(root, f"{script} -h", [str(executable), "-h"]))
    return results


def run_release_gate(
    root: Path,
    *,
    quick: bool = False,
    offline: bool = False,
) -> int:
    root = root.expanduser().resolve()
    out = root / "build" / "release-evidence"
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")

    project, version, scripts = _project_metadata(root)
    _require("pytest", "ruff", "mypy")
    checks: list[dict[str, object]] = []
    if shutil.which("git") and (root / ".git").exists():
        checks.append(_run(root, "git diff --check", ["git", "diff", "--check"]))
    checks.extend(
        [
            _run(
                root,
                "compileall",
                [sys.executable, "-m", "compileall", "-q", "src", "tests"],
            ),
            _run(root, "ruff", [sys.executable, "-m", "ruff", "check", "src", "tests"]),
            _run(root, "mypy", [sys.executable, "-m", "mypy", "--strict", "src"]),
            _run(root, "pytest", [sys.executable, "-m", "pytest", "-q"]),
        ]
    )
    for name, path in (
        ("security scan", root / "scripts" / "security-scan.py"),
        ("safety evaluations", root / "scripts" / "run-evals.py"),
    ):
        if path.exists():
            checks.append(_run(root, name, [sys.executable, str(path)]))

    artifacts: list[dict[str, object]] = []
    if not quick:
        _require("pip_audit", "build")
        checks.append(_run(root, "dependency audit", [sys.executable, "-m", "pip_audit"]))
        out.mkdir(parents=True, exist_ok=True)
        sbom = root / "scripts" / "generate-sbom.py"
        if sbom.exists():
            checks.append(
                _run(
                    root,
                    "generate SBOM",
                    [
                        sys.executable,
                        str(sbom),
                        "--output",
                        str(out / "sbom.cdx.json"),
                    ],
                )
            )
        if (root / "dist").exists():
            shutil.rmtree(root / "dist")
        checks.append(_run(root, "build", [sys.executable, "-m", "build"]))
        wheels = sorted((root / "dist").glob("*.whl"))
        if wheels:
            checks.extend(_wheel_smoke(root, wheels[-1], scripts, offline=offline))
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
        for path in sorted([*(root / "dist").glob("*"), out / "sbom.cdx.json"]):
            if path.is_file():
                artifacts.append(
                    {
                        "path": str(path.relative_to(root)),
                        "size": path.stat().st_size,
                        "sha256": _digest(path),
                    }
                )

    out.mkdir(parents=True, exist_ok=True)
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    report = {
        "schema": "sentinel-forge.local-release-gate.v1",
        "project": project,
        "version": version,
        "python": sys.version,
        "platform": sys.platform,
        "status": status,
        "offline_runtime_layer": offline,
        "checks": checks,
        "artifacts": artifacts,
        "wheelhouse": os.environ.get("SENTINEL_FORGE_WHEELHOUSE"),
    }
    report_path = out / "release-gate.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for item in checks:
        print(f"[{item['status']}] {item['name']}")
        if item["status"] == "FAIL" and item["output_tail"]:
            print(item["output_tail"])
    print(f"Evidence: {report_path}")
    return 0 if status == "PASS" else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Local Sentinel Forge release gate")
    parser.add_argument("--quick", action="store_true", help="Skip audit, build and wheel smoke")
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Use the current machine's validated runtime dependency layer and install "
            "the built wheel with --no-deps"
        ),
    )
    args = parser.parse_args(argv)
    project_root = root or Path.cwd()
    return run_release_gate(project_root, quick=args.quick, offline=args.offline)
