#!/usr/bin/env python3
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".pytest_cache", ".mypy_cache"}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github-token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"),
    "aws-access-key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "slack-token": re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".yml", ".yaml", ".json", ".txt", ".sh", ".cmd", ".tsx", ".ts", ".js"}


def files():
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in SKIP for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_SUFFIXES or path.name in {"Dockerfile"}:
            yield path


def scan_secrets(path: Path, text: str, findings: list[str]) -> None:
    for name, pattern in SECRET_PATTERNS.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            findings.append(f"{path.relative_to(ROOT)}:{line}: high-confidence secret pattern: {name}")


def scan_python(path: Path, text: str, findings: list[str]) -> None:
    if path.suffix != ".py" or "tests" in path.parts:
        return
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        findings.append(f"{path.relative_to(ROOT)}:{exc.lineno}: syntax error during security scan")
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if name in {"eval", "exec"}:
                findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: dangerous dynamic execution: {name}")
            for kw in node.keywords:
                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                    findings.append(f"{path.relative_to(ROOT)}:{node.lineno}: subprocess shell=True")


def main() -> int:
    findings: list[str] = []
    for path in files():
        text = path.read_text(encoding="utf-8", errors="replace")
        scan_secrets(path, text, findings)
        scan_python(path, text, findings)
    if findings:
        print("Security scan findings:")
        print("\n".join(findings))
        return 1
    print("Security scan: no high-confidence secrets or forbidden Python execution patterns found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
