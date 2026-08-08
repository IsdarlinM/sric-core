# Test Evidence — SRIC Core v0.5.0 Release Candidate

## Release-candidate review — 2026-08-08

The `agent/release-0.5.0` branch contains:

- `SentinelCase`, evidence-linked case artifacts and validation recipes;
- deterministic cross-tool claim fingerprints and evidence-adequacy measurement;
- automated correlation restricted to `INFERRED` / `HYPOTHESIS`;
- compatibility-aware Capability Registry that does not import sibling product code;
- `sric capabilities` and the capability API;
- shared Standalone Product Contract gate and six-repository standalone conformance gate;
- Linux/Windows standalone/install CI matrices and SRIC installer preservation smoke definitions;
- release evidence bound to Git commit SHA, tree SHA and dirty state when available;
- coordinated ecosystem smoke and local internal wheelhouse support.

## Fresh execution status

**THE COMPLETE v0.5.0 TEST/RELEASE GATES HAVE NOT EXECUTED SUCCESSFULLY FOR THIS BRANCH.**

This runtime can read and modify the private repository through the authenticated GitHub connector, but cannot materialize it as a complete local checkout. The latest observed GitHub Actions run pattern terminates with `startup_failure` before creating jobs; zero-job workflow attempts are not considered test evidence.

No v0.5.0 pytest, static-analysis, installer, build or release result is claimed from a workflow that never started a job.

## Required exact-commit evidence

From a directory containing the six 0.5 candidate checkouts:

```bash
python -m sric.standalone_gate --root sric-core
python sric-core/scripts/release-standalone-ecosystem.py --root .
python sric-core/scripts/release-gate.py
python sric-core/scripts/release-ecosystem.py --root .
```

Release requires PASS for:

- every product `standalone-gate.json`;
- `ecosystem-standalone-gate.json`;
- every repository `release-gate.json`;
- `ecosystem-release-gate.json`;
- platform installer/update/browser-E2E evidence tied to the same release tree.

Previous targeted QA and older validated baselines remain regression context only; they are not proof that v0.5.0 passed.
