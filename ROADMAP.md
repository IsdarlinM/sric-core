# Roadmap

## Current — 0.5.0 release candidate

Implemented in the 0.5 train:
- Shared `SentinelCase` investigation contract, cross-tool claim fingerprints and evidence adequacy.
- Automated correlation truth-state guard: correlation can emit only `INFERRED` or `HYPOTHESIS`.
- Validation recipes with Scope/Policy action classes and mandatory approval for mutating plans.
- Compatibility-aware Capability Registry and Standalone Product Contract.
- Every product can depend directly on SRIC without requiring sibling Sentinel Forge products.
- Standalone CLI/API/Web contracts, cross-platform installer smokes and data-preserving Linux uninstall behavior.
- CLI/API surfaces for case inspection, claim fingerprinting and capability discovery.
- Release-evidence schema v2 with commit/tree identity.
- Coordinated six-repository standalone gate, integrated release gate, deterministic ecosystem contract smoke and local internal wheelhouse.
- Linux/Windows CI definitions; GitHub-hosted workflow execution is currently blocked by an external startup failure and is not counted as evidence.

## 0.6.0 — Operator Experience & Composable Research

### Safe Web Research Command Console
- Add a terminal-like Web experience generated from the registered product command schema.
- It MUST NOT expose `bash`, PowerShell, `cmd.exe`, arbitrary subprocess execution or unrestricted filesystem commands.
- Commands are parsed into typed operation requests and pass through `Scope -> Policy -> Rate Limits -> Approval -> Executor` when active.
- Show action class, scope decision, policy decision and approval state before execution.
- Support command history, completion, searchable help, dry-run/preview, cancel/retry for jobs and structured JSON/table/graph/timeline output.
- Link every result directly to evidence/provenance and the originating Sentinel Case.
- Loopback-only by default; authenticated TLS/RBAC remote mode remains deferred until threat-modeled and tested.

### Shared command schema
- Generate CLI and Web forms from one versioned command/argument schema so CLI/Web capabilities cannot drift.
- Give every public operation a stable command ID, action class, required permissions and documented output schema.
- Add model-based and pairwise argument testing for each registered command in addition to recursive help/parser tests.

### Capability Registry v2
- Replace the first-party-only central catalog with signed/data-only capability manifests discoverable through package metadata.
- Third-party plugins/products may advertise capabilities without executing code during discovery.
- Add compatibility ranges, permissions, provenance, conflicts and capability dependency resolution.

### Shared Workspace Profiles
- Add an explicit `~/.sentinel-forge/workspaces` shared profile while preserving each product's standalone workspace mode.
- Support safe link/adopt/migrate workflows with preview, backup and rollback.
- Show which product namespaces are present in a workspace without forcing installation of those products.

### Cross-product Case Navigator
- One evidence-native Case view that can open observations from FossilScope, authorization coverage from AuthTwin, trust paths from TrustBoundary, organization relationships from Exposure DNA and deterministic RCAP evidence from ReproSec.
- Capability-aware navigation: UI elements appear only when a real compatible capability is available.

### Web/UI quality gate
- Add Playwright E2E on desktop and mobile viewports for every product.
- Test keyboard navigation, accessibility, responsive layouts, browser console errors, job/SSE reconnect behavior and evidence drawers.
- Add visual layout regression checks without turning screenshots into truth/evidence of security findings.

### Precision and research yield
- Central Calibration Registry for evidence adequacy, reproducibility, source independence, currentness, research priority and uncertainty as separate dimensions.
- Skeptic v2 with competing explanations, counter-evidence requests and deterministic falsification recipes.
- Cross-product research eval corpus with precision/recall, false-positive rate, Brier score, ECE, abstention accuracy and precision@K.

### Reliability and scale
- SQLite WAL/index/query optimization and performance budgets before introducing additional infrastructure.
- Durable multi-process job leases, bounded concurrency and resumable imports/analysis.
- Corpus/property fuzzing for hostile import formats and migration state.
- Signed release attestations, release channels and migration rollback orchestration.

## Later / 1.0
- Stable schemas/API and plugin/capability SDK.
- Audited security and threat models.
- Reproducible signed releases and external conformance fixtures.
- Documented support/deprecation policy.
- Authenticated collaboration/RBAC only after the local-first security model is stable and independently reviewed.
