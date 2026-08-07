# Bitemporal evidence and chain of custody

SRIC 0.4.1 separates two independent timelines:

- **valid time**: when a fact was true in the researched system;
- **knowledge time**: when Sentinel Forge recorded and knew that fact.

`BitemporalBounds` contains `valid_from`, optional `valid_to`, `recorded_at` and optional `superseded_at`. Queries must provide both a valid-time instant and a knowledge-time instant. This prevents a historical reconstruction from using evidence learned later.

Simultaneously visible records with incompatible values are returned by `detect_temporal_conflicts`. They must remain `UNKNOWN` until reconciled; the framework never selects a convenient value silently.

## Evidence-set integrity

`EvidenceDigest`, `evidence_merkle_root`, `build_merkle_proof` and `verify_merkle_proof` provide deterministic SHA-256 Merkle roots and inclusion proofs. Domain-separated leaf and internal-node hashing prevents structural ambiguity. Evidence IDs must be unique.

A Merkle root proves membership and tamper detection for the committed evidence set. It does not prove that the evidence is truthful, complete or correctly interpreted.

## Source independence

`SourceProfile` records authority, source type, upstream providers, independence groups, freshness, manipulation risk, expected coverage, terms and known limitations. `resolve_source_independence` groups mirrors and derived providers by upstream origin, reports unresolved dependencies and conservatively collapses dependency cycles.

Source count and independent-source count are different metrics. Unknown upstream lineage never increases confidence.
