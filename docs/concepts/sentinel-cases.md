# Sentinel Case

`SentinelCase` is the shared investigation container introduced in SRIC 0.5.0.

It groups evidence-linked artifacts from ReproSec, AuthTwin, FossilScope, TrustBoundary Mapper and Exposure DNA without allowing one product to silently promote another product's inference.

## Truth-state safety

Case artifacts use the SRIC claim states: `OBSERVED`, `INFERRED`, `HYPOTHESIS`, `VALIDATED`, `REJECTED` and `UNKNOWN`.

A case is an organizational container only. Adding an artifact to a case never changes its truth state. A `VALIDATED` artifact must reference evidence.

Automated correlation is restricted separately to `INFERRED` and `HYPOTHESIS`.

## Validation recipes

A validation recipe records the smallest deterministic experiment proposed to resolve uncertainty. Recipes contain an action class, target, method, success predicate and required evidence references.

`OUT_OF_SCOPE` and `PROHIBITED` actions are rejected. Mutating recipes require explicit human approval. Execution still passes through Scope Engine, Policy Engine, rate limits, approval and the executor.

## Cross-tool fingerprints

`claim_fingerprint()` creates a deterministic identifier from a normalized subject/predicate/object/context tuple. Products should use this identifier to deduplicate semantically identical candidate claims while preserving their independent evidence and provenance.

## Evidence adequacy

`evidence_adequacy()` measures how much required evidence is present. It is a coverage metric only and can never validate a claim.
