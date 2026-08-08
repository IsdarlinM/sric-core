# Security Research Intelligence Core (SRIC)

```text
SRIC Core :: v0.5.2
Developer: IsdarlinM

Evidence-native shared core for security research intelligence.
```

Shared evidence-native runtime and interoperability layer for ReproSec, AuthTwin, FossilScope, TrustBoundary Mapper and Exposure DNA.

> **AI proposes. Evidence proves. Humans control.**

## Product model

Every Sentinel Forge product is independently installable and independently useful. SRIC is the shared runtime dependency, not a requirement to install the entire kit.

```text
ReproSec ---------\
AuthTwin ----------\
FossilScope --------> SRIC Core
TrustBoundary -----/
Exposure DNA -----/
```

Sibling products are optional capabilities. SRIC discovers installed, release-train-compatible products through package metadata without importing or executing sibling code:

```bash
sric capabilities
sric capabilities --product fossilscope
```

An installed but incompatible product is reported as present but does not publish capabilities.

## Implemented

- typed truth states: `OBSERVED`, `INFERRED`, `HYPOTHESIS`, `VALIDATED`, `REJECTED`, `UNKNOWN`;
- `SentinelCase` investigation contract with evidence/counter-evidence and validation recipes;
- deterministic cross-tool claim fingerprints and evidence-adequacy measurement;
- automated correlation structurally restricted to `INFERRED`/`HYPOTHESIS`;
- content-addressed evidence store with SHA-256 integrity checks and size limits;
- Scope Engine, Policy Engine, rate limits, approval gates and redirect revalidation;
- structured redaction, audit logging and secret-safe defaults;
- provider-neutral AI abstraction with AI disabled by default;
- plugin manifest/type/permission model with isolation primitives;
- Shared Ecosystem Workspace v2 and Temporal Security Knowledge Graph v2;
- persistent cancellable Job/Event Engine with SSE;
- Evidence Lineage, Research Notebook and saved queries;
- hostile import preflight and explicit untrusted-data prompt boundaries;
- role-separated Cartographer, Historian, Security Analyst, Validator, Skeptic, Evidence Agent and Orchestrator primitives;
- Secret Vault abstraction;
- versioned safety/AI evals;
- signed Ed25519/SHA-256 wheel update primitive;
- compatibility-aware first-party Capability Registry;
- shared Standalone Product Contract gate and ecosystem standalone conformance gate;
- shared professional CLI presentation with subdued green banners, Rich help and `--no-color`/`NO_COLOR` support.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
sric doctor
sric capabilities
```

## CLI presentation

Interactive terminals display a compact subdued-green banner ordered as `SRIC Core :: v0.5.2`, `Developer: IsdarlinM`, then a brief purpose statement. Use `sric --no-color COMMAND`, `sric COMMAND --no-color`, or the standard `NO_COLOR` environment variable for plain terminal output. Presentation is kept off machine-readable stdout; see `docs/cli-presentation.md`.

## Validation

Standalone contract:

```bash
python -m sric.standalone_gate --root .
```

Full repository gate:

```bash
python scripts/release-gate.py
```

Six-product standalone conformance from sibling checkouts:

```bash
python sric-core/scripts/release-standalone-ecosystem.py --root .
```

Integrated release train:

```bash
python sric-core/scripts/release-ecosystem.py --root .
```

Machine-readable evidence is written below `build/release-evidence/`. A release requires PASS tied to the exact source commit/tree.

## Safety defaults

Telemetry, cloud AI and external uploads are OFF. Non-loopback API binding is rejected until authenticated TLS mode exists. Scope and Policy are deterministic components outside the LLM boundary.

The master blueprint remains normative. Features not listed as implemented must not be presented as complete.
