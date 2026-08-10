# Sentinel Forge 0.5.13 stabilization status

Date: 2026-08-10

SRIC Core 0.5.13 is in a stabilization cycle and must not be described as a fully gated stable release until the release criteria below execute successfully.

## Freeze

New 0.6 feature work is paused behind P0/P1 stabilization. AI-derived analysis remains non-authoritative: AI proposes, evidence proves, humans control.

## Current release blockers

- Hosted GitHub Actions cannot currently allocate runners; zero-step failures are not test failures and are not PASS.
- Complete Windows/Linux and Python 3.11/3.12/3.13 gates must execute.
- The ecosystem dependency audit identified open review items for Click, Cryptography and Starlette locks. No exception is accepted without a dated mitigation and compatibility evidence.
- Signed tags/releases, SBOM, build provenance and exact test evidence are required before stable publication.

## P0/P1 stabilization scope

- canonical CLI-to-Web parameter typing and argv round-trip validation;
- explicit/fail-closed mutation approval;
- Python 3.11 Web import compatibility;
- data-preserving Windows/Linux uninstall contracts;
- cross-repository CI pinned to exact public first-party commits;
- controlled 4xx API errors and same-origin API documentation in product applications.

The moving update channel must not be advanced solely because code is merged. Release-channel movement requires the complete release gate and evidence for the exact commit.
