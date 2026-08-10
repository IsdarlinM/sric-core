# Security Research Intelligence Core (SRIC)

```text
SRIC Core :: v0.5.13
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
- guided **Web Security Console** derived from the real public Typer capability tree, with operation cards, typed controls, approval UX, live jobs and output;
- JSON-safe capability metadata including choices, numeric bounds, path semantics, defaults and defensive normalization;
- fixed-runner Web execution with `shell=False`, disabled stdin and no browser-selected executable;
- structured redacted HTTP 503 handling for capability-catalog failures;
- bounded Web child-process terminate/kill/reap behavior and retained terminal-job tombstones for SSE/status readers;
- redacted Job Engine errors/events/metadata/provenance before persistence.

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

The 0.5.13 installers remain idempotent and repair-capable. They validate both the selected host Python and an existing virtual-environment interpreter; an obsolete/broken runtime causes only the isolated `venv` to be rebuilt, never workspaces or configuration. They bootstrap `pip`, `setuptools` and `wheel`, run `pip check`, import-probe the shared Web runtime and smoke-test all root help forms before reporting success.

Installer-internal CLI smokes run with `SENTINEL_BANNER=never` and write their output to a temporary validation log. A successful installation therefore does not print the product banner repeatedly; if a validation fails, the captured diagnostic output is printed before the installer exits non-zero.

On Termux, a writable `$PREFIX/bin` already present in `PATH` is preferred so the command becomes immediately reachable. Standard Linux falls back to `~/.local/bin` and persists the canonical `export PATH="$HOME/.local/bin:$PATH"` line when required. Windows accepts any Python 3 interpreter that satisfies `>=3.11`; user PATH changes are centralized in `sric.install_path`, which updates `HKCU\Environment\Path` without `setx` truncation and broadcasts `WM_SETTINGCHANGE`.

## Development install

```bash
python -m venv .venv
. .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e '.[dev]'
sric doctor
sric capabilities
```

## CLI presentation

Interactive terminals display a compact subdued-green banner ordered as `SRIC Core :: v0.5.13`, `Developer: IsdarlinM`, then a brief purpose statement. Use `sric --no-color COMMAND`, `sric COMMAND --no-color`, or the standard `NO_COLOR` environment variable for plain terminal output. Presentation is kept off machine-readable stdout; see `docs/cli-presentation.md`.

Unexpected operational exceptions are contained and redacted by default. Developers can opt into raw local exception propagation with `SENTINEL_DEBUG=1`; this switch is not intended for normal user operation.

## Guided Web Security Console

`sric web` opens `/workbench`, the primary guided Security Console. The browser does **not** expose a command box, a free-form argv field, option-name entry, or an operating-system shell. The historical `/console` route is retained only as a compatibility alias that opens the guided interface.

The Security Console is generated from the same installed Typer capability tree as the CLI so product behavior remains single-sourced. Every public command still has a Web operation and every ordered CLI parameter remains represented, but users interact through UI semantics rather than command syntax:

- flags become checkboxes or explicit Default / Enabled / Disabled selectors;
- closed choices become combo boxes or multi-select controls;
- numeric values use number controls with available bounds;
- fixed-arity and repeated values use structured list/value controls;
- paths use path-oriented fields;
- secret-like values use protected password-style controls;
- optional settings require an explicit `Customize this setting` choice before being included.

`/api/v1/workbench/coverage` reports a contract failure if a CLI capability or parameter disappears from Web representation. Catalog metadata is normalized to JSON primitives before it reaches FastAPI, including `Path`, enum/container values, choices and numeric bounds. Malformed metadata is bounded and cyclic command trees are rejected explicitly.

Internally, selected controls are deterministically serialized to argv only as a transport detail and submitted to the fixed Python runner. `shell=False`, disabled stdin, redaction, bounded execution, SSE output, cancellation and Scope/Policy/Rate/Approval controls remain authoritative. The browser cannot choose an executable or supply arbitrary command syntax.

Mutating operations expose an explicit human-approval checkbox. Destructive operations add a second impact acknowledgement; the backend destructive-approval contract remains enforced without asking the user to memorize/type a CLI phrase.

Timed-out child commands use bounded terminate/kill/wait handling. If a child still cannot be synchronously reaped after forced termination, the Web runtime records a controlled terminal state and engages a bounded background reaper rather than blocking the request worker indefinitely. Recently pruned terminal jobs remain available briefly to already-active status/SSE readers to avoid prune/read races.

Desktop presents Operations, Configure and Recent Activity panels. Mobile switches between those sections with touch-friendly controls. See `docs/web/feature-workbench.md`, `docs/web/cli-parity.md`, and `docs/runtime-compatibility.md`.

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

The 0.5.13 regressions add coverage for guided-control mapping, exact CLI/Web parameter coverage, absence of free-form argv entry, same-origin Web assets, mutation approval and existing fixed-runner safety invariants.

Hosted GitHub Actions for this candidate are currently unable to allocate runners because GitHub reports the account as locked due to a billing issue. Those jobs contain zero executed steps, so they are an external validation blocker and are not claimed as PASS or as code-test failures. Machine-readable release evidence requires PASS tied to the exact source commit/tree before the release can be considered fully validated.

## Safety defaults

Telemetry, cloud AI and external uploads are OFF. Non-loopback API binding is rejected until authenticated TLS mode exists. Scope and Policy are deterministic components outside the LLM boundary.

The master blueprint remains normative. Features not listed as implemented must not be presented as complete.
