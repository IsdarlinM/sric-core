# Local release validation

Sentinel Forge does not depend on GitHub Actions or another hosted CI service. Every repository ships a local, cross-platform release gate at `scripts/release-gate.py`.

Run the complete gate from an isolated development environment:

```bash
python -m pip install -e '.[dev]'
python scripts/release-gate.py
```

For an offline smoke test that installs the built wheel without resolving dependencies:

```bash
python scripts/release-gate.py --offline
```

A fast developer pass is available, but it is not sufficient for a release:

```bash
python scripts/release-gate.py --quick
```

The full gate performs:

- Python compilation;
- Ruff and strict mypy;
- unit, integration, security and E2E pytest suites;
- project security scan and safety/AI evaluations when present;
- dependency audit with `pip-audit`;
- SBOM generation when supported by the repository;
- wheel and source-distribution build;
- isolated wheel installation;
- root CLI `--help` and `-h` smoke tests;
- SHA-256 hashes for generated release artifacts.

The machine-readable result is written to `build/release-evidence/release-gate.json`. A release must not be announced when its status is `FAIL`, when required tools are missing, or when the report does not correspond to the exact source commit being released.

No production secrets, target credentials, capsules or workspace data are required by the release gate.
