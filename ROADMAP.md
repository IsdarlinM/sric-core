# Roadmap

## Current — 0.3.x hardening

Implemented foundations include the temporal graph, evidence/provenance lineage, bounded/cancellable job engine with SSE events, explainable correlation rules, safe import preflight, research notebook/saved queries, read-only graph query language, permission-declared plugin broker, provider-neutral AI abstraction, external-data prompt boundary, explicit AI budget/preview, and signed-update verification.

Remaining hardening before 0.4:
- OS-backed encrypted secret vault/keyring abstraction and evidence-retention encryption.
- Durable database-backed multi-process job queue while preserving local-first single-user defaults.
- Plugin isolation strategy for untrusted third-party code (out-of-process sandbox); in-process broker remains trusted-plugin only.
- Stable versioned public Python/API SDK contracts and migration compatibility matrix.
- Full backup/rollback orchestration around schema migrations and stable release trust-root bootstrap.

## 0.4–0.8
- Performance/large-graph virtualization primitives.
- Richer correlation DSL and conformance datasets.
- Optional collaboration primitives only after authentication/RBAC threat modeling.

## 1.0
Stable schemas/API, audited security model, reproducible signed releases, documented support/deprecation policy and external conformance cases.
