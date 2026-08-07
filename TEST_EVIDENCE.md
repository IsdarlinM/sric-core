# Test Evidence — SRIC Core v0.4.1

## QA pass — 2026-08-07

Current source changes were audited through the authenticated GitHub connector and the high-risk changed modules were reconstructed in the local runtime.

Freshly executed in this QA pass:

- targeted SRIC unit regression matrix for bitemporal evidence, confidence/Skeptic calibration, source independence, Merkle integrity and SDK/interchange logic: **15 passed**;
- Python `compileall` over the reconstructed corrected modules: **PASS**;
- cross-product Sentinel Forge high-risk regression matrix: **7 passed** across ReproSec, AuthTwin, FossilScope, TrustBoundary and Exposure DNA;
- branch comparison against `main`: branch is ahead and **0 commits behind** at the time of this audit.

Additional regression tests were added for:

- canonical bitemporal comparisons;
- reserved JSON-LD fields and duplicate graph IDs;
- dependency cycles overriding declared source independence;
- API input-domain and controlled 4xx error handling;
- every registered CLI help path through the real vNext entrypoint;
- `sric web` serving the same vNext API that exposes evidence-native routes;
- CLI claim-transition errors returning controlled exit codes instead of tracebacks.

## Current release-gate status

**FULL LOCAL RELEASE GATE NOT EXECUTABLE IN THIS RUNTIME.**

The repositories are private and the runtime cannot resolve or connect to `github.com` / `raw.githubusercontent.com`, so a complete checkout cannot be materialized outside the GitHub connector. The connector exposes individual blobs but not a mountable repository archive. Therefore the complete current `pytest` tree, build/install smoke and every unchanged historical test cannot honestly be reported as freshly executed here.

The following release tools are also unavailable in the runtime and cannot be installed from its package index:

- Ruff;
- mypy;
- `build`;
- `pip-audit`.

No GitHub Actions, Codespaces or other hosted/paid GitHub execution was used.

Do not describe v0.4.1 as a fully validated release until the exact commit produces `PASS` from a complete sibling checkout using:

```bash
python -m pip install -e '.[dev]'
python scripts/release-gate.py
python scripts/release-ecosystem.py --root ..
```

## Previous validated baseline

The previous v0.4.0 source state was recorded on 2026-07-22 with:

- pytest: **57 passed**;
- compileall: **PASS**;
- security scan: **PASS**;
- CLI help coverage: **PASS** for 43 registered command paths;
- synthetic/local functional smoke: **PASS**;
- wheel build and isolated wheel smoke against the then-validated runtime dependency layer: **PASS**.

Those historical results apply only to the previous v0.4.0 state. They are a regression baseline, not proof of v0.4.1.
