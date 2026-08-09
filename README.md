# Security Research Intelligence Core (SRIC)

```text
SRIC Core :: v0.5.4
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
- signed Ed25519/SHA-256 wheel update primitive with safe same-version `--force` reinstall support;
- compatibility-aware first-party Capability Registry;
- shared Standalone Product Contract gate and ecosystem standalone conformance gate;
- shared professional CLI presentation with subdued green banners, Rich help and `--no-color`/`NO_COLOR` support;
- shared Web Command Console that derives its command catalog from the installed Typer CLI and provides controlled Web/CLI capability parity without exposing an operating-system shell.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
sric doctor
sric capabilities
```

## CLI presentation

Interactive terminals display a compact subdued-green banner ordered as `SRIC Core :: v0.5.4`, `Developer: IsdarlinM`, then a brief purpose statement. Use `sric --no-color COMMAND`, `sric COMMAND --no-color`, or the standard `NO_COLOR` environment variable for plain terminal output. Presentation is kept off machine-readable stdout; see `docs/cli-presentation.md`.

## Web/CLI parity

` sric web ` now exposes the Web Command Console at `/console`; the root Web URL redirects there. The catalog is generated from the installed Typer command tree, so new public CLI commands become visible to the Web console without maintaining a second hand-written feature list.

The console is deliberately **not** an operating-system shell. The browser submits an exact CLI command plus an argv array. SRIC launches only the fixed `sric.web_console_runner` with `shell=False`; the browser cannot select an executable or execute shell metacharacters. Mutating commands require explicit approval, destructive command names require a typed approval phrase, and the `web` command is context-only because the server is already running.

Jobs are isolated in subprocesses, limited to two concurrent executions by default, capped at 30 minutes and 1 MB of retained output, cancellable, and streamed to the browser with SSE. Arguments and output pass through secret redaction before they are retained by the in-memory console job view. A per-process anti-CSRF token is required for command submission and cancellation.

See `docs/web/cli-parity.md` for the API and security contract.

## Signed updates

The production updater accepts only a trusted Ed25519-signed manifest and a SHA-256 verified wheel; it never uses blind `git pull`. A release channel can be supplied with `--manifest`/`--public-key` or configured through `SRIC_RELEASE_MANIFEST_URL` and `SRIC_RELEASE_PUBLIC_KEY`.

```bash
sric update --check --manifest release.json --public-key release.pub.pem
sric update --manifest release.json --public-key release.pub.pem
sric update --force --manifest release.json --public-key release.pub.pem
```

`--force` reinstalls the selected signed release even when that same version is already installed. It may install a newer signed version, but never downgrades. `--check` and `--force` cannot be combined. A default trust root is intentionally not embedded until the official signing channel is published.

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
