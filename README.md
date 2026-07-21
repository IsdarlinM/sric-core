# Security Research Intelligence Core (SRIC)

```text
SRIC CORE
imr :: v0.3.0
```

Shared evidence-native primitives for ReproSec, AuthTwin, FossilScope, TrustBoundary Mapper and Exposure DNA.

> **AI proposes. Evidence proves. Humans control.**

## Implemented in v0.3.0

- Typed truth states: `OBSERVED`, `INFERRED`, `HYPOTHESIS`, `VALIDATED`, `REJECTED`, `UNKNOWN`.
- Claim-Evidence Contract models with evidence and counter-evidence references.
- Content-addressed evidence store with SHA-256 integrity checks and size limits.
- Scope Engine with allow/deny rules, method policy, redirect revalidation and private/special-network SSRF controls.
- Deterministic Policy Engine with action classes and separate preflight/human approval semantics.
- Conservative HTTP action classifier: GET/HEAD are not automatically safe; DELETE is destructive by default.
- Shared global/per-host active-request rate limiter.
- Structured redaction primitives for headers/text, query parameters, JSON and form-urlencoded data.
- Audit logging with query-secret redaction.
- Provider-neutral AI abstraction; AI disabled by default and unable to bypass Scope/Policy.
- Plugin manifest/type/permission model; plugins are not auto-executed.
- SQLite/SQLAlchemy storage foundation with Alembic migration baseline.
- Isolated workspaces.
- Local FastAPI health API with restrictive security headers.
- CLI with doctor, workspaces, plugins, AI status, scope checks, signed-release updater, local API and version.
- Signed Ed25519/SHA-256 wheel update primitive; HTTP manifests are rejected and blind production `git pull` is not used.

- Persistent local-first Temporal Graph with temporal snapshots, search and typed evidence-bearing relationships.
- Persistent cancellable Job/Event Engine with SSE event streaming for real-time consumers.
- Evidence Lineage API, reproducible Research Notebook, saved queries and explainable correlation rules.
- Hostile import preflight for files/ZIPs and explicit untrusted-data prompt boundaries.
- Role-separated Cartographer/Historian/Security Analyst/Validator/Skeptic/Evidence Agent/Orchestrator proposal primitives; no agent owns an unrestricted executor.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
pytest
sric doctor
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
