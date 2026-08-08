# Roadmap

## Current — 0.5.0 release candidate

Implemented in the 0.5 train:
- Shared `SentinelCase` investigation contract, cross-tool claim fingerprints and evidence adequacy.
- Automated correlation truth-state guard: correlation can emit only `INFERRED` or `HYPOTHESIS`.
- Validation recipes with Scope/Policy action classes and mandatory approval for mutating plans.
- CLI/API surfaces for case inspection and claim fingerprinting.
- Release-evidence schema v2 with commit/tree identity.
- Coordinated six-repository release gate, deterministic ecosystem contract smoke and local internal wheelhouse.
- Linux/Windows CI definitions; GitHub-hosted workflow execution is currently blocked by an external startup failure and is not counted as evidence.

## Next hardening
- Database-backed multi-process job repository while preserving local-first operation.
- Stronger OS sandbox profiles for third-party plugins.
- Stable public SDK compatibility matrix and migration rollback orchestration.
- Larger graph/performance benchmarks, browser E2E and calibrated cross-product research eval corpus.
- Signed release attestations and external conformance fixtures.

## 1.0
Stable schemas/API, audited security model, reproducible signed releases, documented support/deprecation policy and external conformance cases.
