# Security Research Intelligence Core (SRIC)

```text
SRIC Core :: v0.5.9
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
- zero-config official GitHub update channel with immutable signature-verified commit snapshots, same-version `--force` reinstall, rollback and state backup;
- explicit custom Ed25519/SHA-256 wheel update override for private release channels;
- first-party runtime compatibility checks and signed-channel repair for stale/corrupt shared runtimes;
- compatibility-aware first-party Capability Registry;
- shared Standalone Product Contract gate and ecosystem standalone conformance gate;
- shared professional CLI presentation with subdued green banners, Rich help and `--no-color`/`NO_COLOR` support;
- complete help aliases: `sric --help`, `sric -h`, `sric help`, `sric COMMAND --help`, `sric COMMAND -h`, and `sric COMMAND help`;
- shared Web Command Console with fixed-runner execution and no operating-system shell;
- shared **Web Feature Workbench** that derives every public feature and every CLI argument/option from the installed Typer tree and renders structured responsive forms, approval controls, live jobs and output.

## Installation

Linux / Termux:

```bash
./scripts/install-linux.sh
sric doctor
sric capabilities
```

Windows:

```cmd
scripts\install-windows.cmd
sric doctor
sric capabilities
```

The 0.5.9 installers are idempotent/repair-capable, bootstrap `pip`, `setuptools` and `wheel`, run `pip check`, import-probe the shared Web runtime and smoke-test all root help forms before reporting success. Windows accepts any installed Python 3 version that is actually `>=3.11` instead of requiring exactly Python 3.11. Linux writes the canonical `export PATH="$HOME/.local/bin:$PATH"` line without embedding literal quote characters in `PATH`.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
sric doctor
sric capabilities
```

## CLI presentation

Interactive terminals display a compact subdued-green banner ordered as `SRIC Core :: v0.5.9`, `Developer: IsdarlinM`, then a brief purpose statement. Use `sric --no-color COMMAND`, `sric COMMAND --no-color`, or the standard `NO_COLOR` environment variable for plain terminal output. Presentation is kept off machine-readable stdout; see `docs/cli-presentation.md`.

## Full Web/CLI feature parity

`sric web` opens the full Web Feature Workbench at `/workbench`. `/console` remains available as an advanced argv-oriented console.

The Workbench is generated from the same installed Typer command tree as the CLI. Each public command receives a structured Web feature definition and every CLI parameter is represented in the same order, including positional arguments, options, flags, paired boolean flags, repeated/count options, variadic values, required state, defaults, help text and sensitive-field handling. `/api/v1/workbench/coverage` reports a parity failure if a CLI command or parameter disappears from Web representation.

The browser does not receive an operating-system shell. Structured Web forms are serialized to argv and submitted to the fixed Python runner used by `/console`, with `shell=False`, disabled stdin, secret redaction, bounded execution, SSE output, cancellation and mutation/destructive approval gates. Product Scope/Policy/Rate/Approval controls remain authoritative.

The interface is responsive: desktop uses feature catalog + runner + jobs panels; mobile exposes those views through compact navigation.

See `docs/web/feature-workbench.md`, `docs/web/cli-parity.md`, and `docs/runtime-compatibility.md`.

## Updates

The normal user path is zero-config:

```bash
sric update --check
sric update
sric update --force
```

No manifest or public-key argument is required for the official channel. SRIC accepts only the hard-coded official repository, resolves an immutable commit, requires GitHub to report that commit as signature-verified, downloads that exact source snapshot, rejects unsafe ZIP content, verifies package name/version, backs up state, installs without a shell, and verifies the installed distribution.

`--force` reinstalls the official selected release even when that exact version is already installed. It may install a newer release but never downgrades. `--check` and `--force` cannot be combined. Normal upgrades require rollback metadata; a same-version forced reinstall uses the verified target snapshot as its recovery package.

Advanced/private channels remain available by explicitly supplying both a signed manifest and Ed25519 public key. Custom channels preserve the Ed25519 manifest + SHA-256 wheel verification contract. The updater never falls back to blind `git pull`.

See `docs/release/official-update-channel.md`.

## Validation

```bash
python -m sric.standalone_gate --root .
python scripts/release-gate.py
python sric-core/scripts/release-standalone-ecosystem.py --root .
python sric-core/scripts/release-ecosystem.py --root .
```

The 0.5.9 installer regression gate verifies the Linux PATH contract, Windows Python selection, dependency integrity checks, shared Web import probes and all root help forms. The existing exhaustive interface gate continues to walk every public command and verify CLI/Web parameter parity.

Machine-readable evidence is written below `build/release-evidence/`. A release requires PASS tied to the exact source commit/tree.

## Safety defaults

Telemetry, cloud AI and external uploads are OFF. Non-loopback API binding is rejected until authenticated TLS mode exists. Scope and Policy are deterministic components outside the LLM boundary.

The master blueprint remains normative. Features not listed as implemented must not be presented as complete.
