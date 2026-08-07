# Security Research Intelligence Core (SRIC)

```text
SRIC CORE
imr :: v0.4.1
```

Shared evidence-native primitives for ReproSec, AuthTwin, FossilScope, TrustBoundary Mapper and Exposure DNA.

> **AI proposes. Evidence proves. Humans control.**

## Implemented

- Typed truth states: `OBSERVED`, `INFERRED`, `HYPOTHESIS`, `VALIDATED`, `REJECTED`, `UNKNOWN`.
- Claim-Evidence Contract v2 with evidence, counter-evidence, assumptions, alternative explanations, temporal validity and deterministic validation history.
- Content-addressed evidence store with SHA-256 integrity checks and size limits.
- Scope Engine with allow/deny rules, method policy, redirect revalidation and private/special-network SSRF controls.
- Deterministic Policy Engine with action classes and separate preflight/human approval semantics.
- Conservative HTTP action classifier: GET/HEAD are not automatically safe; DELETE is destructive by default.
- Shared global/per-host active-request rate limiter.
- Structured redaction for headers/text, query parameters, JSON and form-urlencoded data.
- Audit logging with query-secret redaction.
- Provider-neutral AI abstraction; AI is disabled by default and cannot bypass Scope or Policy.
- Plugin manifest/type/permission model with process isolation and artifact-hash verification primitives.
- SQLite/SQLAlchemy storage foundation with Alembic migration baseline and optional explicit PostgreSQL configuration.
- Shared Ecosystem Workspace v2 with stable IDs, namespaces, locking, migrations, backup/restore and integrity checks.
- Temporal Security Knowledge Graph v2 with evidence-bearing relationships and bounded read-only queries.
- Persistent cancellable Job/Event Engine with DAG dependencies, budgets, resumable metadata and SSE events.
- Evidence Lineage API, reproducible Research Notebook and saved queries.
- Hostile import preflight for files/ZIPs and explicit untrusted-data prompt boundaries.
- Role-separated Cartographer, Historian, Security Analyst, Validator, Skeptic, Evidence Agent and Orchestrator proposal primitives.
- Secret Vault abstraction preferring OS keyring and encrypted-file fallback.
- Versioned safety/AI eval runner covering prompt injection, false ownership/auth, temporal confusion, fake evidence, unsafe validation and scope expansion.
- Signed Ed25519/SHA-256 wheel update primitive; HTTP manifests and blind production `git pull` are rejected.

## Precision and false-positive controls in v0.4.1

SRIC now exposes shared confidence-calibration primitives for all Sentinel Forge products:

- source-group deduplication prevents mirrors and derived feeds from inflating confidence;
- temporal half-life discounts stale observations;
- direct/derived evidence, source quality and signal specificity are explicit;
- missing required evidence lowers confidence and forces Skeptic abstention;
- counter-evidence and alternative explanations can reduce or reject a candidate;
- confidence remains advisory and cannot create a `VALIDATED` finding;
- Brier score and Expected Calibration Error support measurable evaluation datasets.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
python -m pytest
sric doctor
```

## Local release gate

This repository does not depend on hosted CI. Run the complete cross-platform release gate locally:

```bash
python scripts/release-gate.py
```

It runs compile checks, Ruff, strict mypy, pytest, security scans, safety evals, dependency audit, SBOM generation, package build, isolated wheel installation and CLI help smoke tests. Machine-readable evidence is written to `build/release-evidence/release-gate.json`.

A quicker non-release pass is available with:

```bash
python scripts/release-gate.py --quick
```

## Safety defaults

Telemetry, cloud AI and external uploads are off. Non-loopback API binding is rejected until authenticated TLS mode exists. Scope and Policy are deterministic components outside the LLM boundary.

## First five minutes

```bash
sric doctor
sric workspace create demo
sric scope check https://api.example.com --allow '*.example.com'
sric ai status
sric --help
```

The master blueprint remains normative. Features not listed as implemented must not be presented as complete.
