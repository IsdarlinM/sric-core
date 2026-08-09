# Changelog

## 0.5.4 - 2026-08-08
- Added a shared Web Command Console that derives its catalog from the installed Typer command tree, keeping Web capability discovery aligned with the public CLI.
- Added fixed-module subprocess execution through `sric.web_console_runner` with `shell=False`, disabled stdin and no browser-controlled executable selection.
- Added explicit approval gates for mutating commands and typed approval phrases for destructive command names; existing product Scope/Policy/rate/approval gates remain authoritative.
- Added per-process anti-CSRF protection for command submission/cancellation, argument/output secret redaction, ANSI/control-character stripping and bounded retained output/runtime/concurrency defaults.
- Added cancellable in-memory console jobs with Server-Sent Events for real-time output and status.
- Added a responsive same-origin `/console` UI and routed `sric web` to it without exposing an operating-system shell.
- Added unit and security regression coverage for real command discovery, nested commands, secret redaction, mutation approval, recursive-Web rejection and a real `sric version` execution through the fixed runner.

## 0.5.3 - 2026-08-08
- Added `update --force` as an explicit reinstall mode for a signed release, including same-version reinstalls via pip `--force-reinstall`.
- Kept downgrade protection: `--force` may install the same or a newer signed version, never an older version.
- Made `--check` and `--force` mutually exclusive and exposed `same_version`, `forced` and `installed` in update status output.
- Preserved Ed25519 manifest verification, SHA-256 wheel verification, state backup and rollback behavior.
- Same-version forced reinstalls use the verified target wheel as the package recovery artifact; normal upgrades still require verified rollback metadata.
- Added security and CLI regression coverage for same-version no-op, force reinstall, pip force flag, downgrade rejection and conflicting flags.

## 0.5.2 - 2026-08-08
- Added shared Sentinel Forge CLI branding primitives with the canonical `Tool :: vX.X.X`, `Developer: IsdarlinM`, description ordering.
- Added a subdued green interactive banner rendered on stderr so redirected and machine-readable stdout remains clean.
- Added global `--no-color` support, `NO_COLOR` compatibility and argument normalization so the flag can be accepted consistently by console entrypoints.
- Enabled Rich/Typer command-help presentation while preserving plain output when color is disabled.
- Added regression tests for exact banner ordering, version/developer rendering, wrapping and no-color behavior.

## 0.5.1 - 2026-08-08
- Added an explicit first-party dependency manifest consumed by both Windows and Linux installers.
- Installer dependency bootstrap is now separated from third-party PyPI resolution so downstream Sentinel Forge products can resolve author-maintained packages from pinned GitHub source archives.
- Kept SRIC itself free of mandatory sibling-product dependencies.

## 0.5.0 - 2026-08-08
- Added the shared `SentinelCase` investigation contract for cross-product observations, hypotheses, evidence, counter-evidence and validation recipes.
- Added deterministic cross-tool claim fingerprints and evidence-adequacy measurement without changing truth state.
- Added `AutomatedCorrelationStatus`; automated correlation is now structurally limited to `INFERRED` or `HYPOTHESIS` and cannot emit `VALIDATED`.
- Added validation-recipe safety guards that reject prohibited/out-of-scope actions and require human approval for mutating validation.
- Added the Standalone Product Contract and compatibility-aware capability discovery without importing sibling product code.
- Added `sric capabilities`, the read-only capability API and a shared standalone gate that verifies dependency isolation, CLI safety and product readiness.
- Added ecosystem standalone conformance evidence so every product must pass independently before the integrated release train can pass.
- Added installer/uninstaller preservation tests and cross-platform clean-install CI contracts for downstream products.
- Added 0.5 regression tests for case integrity, evidence gates, capability compatibility and automated-correlation state safety.
- Added least-privilege GitHub Actions CI across Linux/Windows and Python 3.11-3.13 plus a full release-gate evidence job.

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
