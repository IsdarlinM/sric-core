# Changelog

## 0.4.1 - 2026-08-06
- Added explainable confidence scoring with source-group deduplication, temporal decay, source quality, specificity and required-evidence completeness.
- Added a mandatory Skeptic review primitive that can retain, reduce, reject or abstain as `UNKNOWN` without validating findings.
- Added Brier score and Expected Calibration Error helpers for measurable false-positive and confidence calibration benchmarks.
- Added regression tests for duplicated upstream sources, stale evidence, missing required evidence, counter-evidence and calibration metrics.
- Replaced hosted GitHub Actions/Dependabot automation with a cross-platform local release gate that runs tests, static checks, security scans, evals, dependency audit, SBOM generation, package build, isolated wheel smoke and CLI help checks.
- Added machine-readable local release evidence and artifact SHA-256 generation.

## 0.4.0 - 2026-07-22
- Added Shared Ecosystem Workspace v2 with locking, migrations, backup/restore, integrity checks and per-product namespaces.
- Added Claim-Evidence Contract v2 with guarded truth-state transitions and deterministic validation history.
- Expanded Temporal Graph and read-only query DSL with explain/path/history/diff, confidence predicates, pagination and complexity limits.
- Added declarative correlation contributions, Job DAG/retry/resource budgets, Secret Vault and process-isolated plugin runner primitives.
- Added built-in safety/evidence eval framework and CLI graph/eval/workspace integrity commands.

## 0.3.0 - 2026-07-21
- Added a persistent temporal graph with typed nodes/edges, temporal snapshots, search and neighbor queries.
- Added persistent cancellable jobs/events plus SSE event streaming for real-time UI/API consumers.
- Added evidence lineage, reproducible research notebook/saved queries and explainable correlation-rule primitives.
- Added hostile import preflight for files/ZIPs with traversal, symlink, entry-count, decompression and compression-ratio controls.
- Expanded plugin registry lifecycle with install/enable/disable/remove/verify while keeping plugin code non-auto-executing.
- Added explicit prompt-boundary labeling for untrusted external data and role-separated agent proposal/Skeptic orchestration primitives.
- Added graph/search/jobs/notebook local API endpoints and CLI commands for query, jobs, notebook, lineage and import-check.

## 0.2.0 - 2026-07-21
- Added structured redaction for query parameters, JSON and form-urlencoded data.
- Added conservative deterministic HTTP action classification shared by active executors.
- Updated audit target sanitation to prevent query-secret leakage.
- Expanded security/unit regression coverage while retaining v0.1 core contracts.

## 0.1.0 - 2026-07-21
- Initial SRIC evidence/provenance models and truth-state contract.
- Scope and Policy engines with separate preflight/approval semantics.
- Shared global/per-host rate limiter for active executor gates.
- Signed Ed25519/SHA-256 wheel update primitive; no blind git-pull updater.
- Evidence store, redaction, audit logging, plugin manifest model and AI abstraction.
- SQLite/Alembic storage foundation, workspaces, CLI and local API.
- Unit, integration, E2E CLI and security tests.
