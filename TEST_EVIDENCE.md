# Test Evidence — SRIC Core v0.5.0 Release Candidate

## Release-candidate review — 2026-08-08

The `agent/release-0.5.0` branch contains the SRIC 0.5 contract changes under review:

- `SentinelCase`, evidence-linked case artifacts and validation recipes;
- deterministic cross-tool claim fingerprints and evidence-adequacy measurement;
- automated correlation restricted by type to `INFERRED` / `HYPOTHESIS`;
- release evidence bound to Git commit SHA, tree SHA and dirty state when available;
- coordinated ecosystem smoke and local internal wheelhouse support;
- new unit regressions for case/evidence safety and correlation truth-state restrictions.

## Fresh execution status

**THE COMPLETE v0.5.0 RELEASE GATE HAS NOT BEEN EXECUTED SUCCESSFULLY FOR THIS BRANCH.**

This runtime can read and modify the private repository through the authenticated GitHub connector, but it cannot materialize the private repository as a local checkout. The local environment also has no authenticated `gh` checkout path.

GitHub Actions workflows were added, but observed workflow runs currently terminate with GitHub `startup_failure` before creating any job or check-run. Historical pre-0.5 workflow runs in this repository show the same zero-job startup failure, so this is recorded as an execution-infrastructure blocker rather than a test PASS or FAIL.

No v0.5.0 test, build, installer or release result is claimed from those failed-to-start workflow runs.

## Required release evidence

From a directory containing all six sibling repositories at their exact 0.5 candidate commits, run:

```bash
python -m pip install build pip-audit pytest ruff mypy hypothesis
python sric-core/scripts/release-ecosystem.py --root .
```

The ecosystem gate builds a local wheelhouse for all six unreleased 0.5 packages, runs each repository release gate, checks internal dependency compatibility and executes the deterministic cross-product contract smoke.

Do not merge/tag a Sentinel Forge 0.5 release until:

- every repository `build/release-evidence/release-gate.json` reports `PASS`;
- `sric-core/build/release-evidence/ecosystem-release-gate.json` reports `PASS`;
- the reports identify the exact commit/tree under release;
- clean-install/update/platform and other release requirements are supported by evidence rather than assumption.

## Historical regression baseline

Previous 2026-08-07 targeted QA and the older v0.4.0 validated baseline remain available in Git history. They are regression context only and are not evidence that v0.5.0 passed.
