# Web Feature Workbench

SRIC Core 0.5.6 introduces a shared structured Web surface for every public CLI feature in Sentinel Forge.

## Contract

The canonical feature source is the installed Typer command tree. `build_feature_catalog()` derives a Web feature for every public CLI command and preserves the original parameter order. The Web schema includes positional arguments, options, flags, paired boolean flags, count/repeated options, multiplicity, arity, required state, default values, type metadata, help text and sensitive-field classification.

`feature_contract()` compares the CLI tree with the Web tree. A complete contract requires:

- identical public command paths;
- identical ordered parameter names for each command;
- no Web-only invented command;
- no CLI-only command omitted from Web.

`/api/v1/workbench/coverage` exposes that result for automated tests and diagnostics.

## Routes

- `/workbench` — structured responsive Web UI for all public features;
- `/api/v1/workbench/catalog` — feature schema and parity contract;
- `/api/v1/workbench/coverage` — machine-readable parity status;
- `/console` — advanced argv-oriented console retained for expert use.

The Workbench is not a separate implementation of product behavior. It serializes structured fields to an argv array and submits them through the same fixed Web Command Console runner. This avoids duplicating feature logic and ensures CLI-side Scope, Policy, rate, approval and evidence controls remain authoritative.

## Security

The Workbench:

- does not expose an operating-system shell;
- cannot select an executable;
- uses the fixed `sric.web_console_runner` path with `shell=False`;
- disables stdin;
- reuses the per-process Web console CSRF token for mutating requests;
- preserves explicit approval for mutating operations and typed approval for destructive operations;
- marks secret-like inputs as sensitive fields and relies on the shared argument/output redaction path before retention;
- consumes same-origin assets and APIs under the existing restrictive CSP;
- streams job state/output through the existing bounded SSE job mechanism.

External/imported content remains untrusted data and is never treated as Web instructions.

## Responsive behavior

Desktop presents a three-panel layout: feature catalog, structured runner and recent jobs. Smaller screens collapse this into explicit Features / Runner / Jobs views so all controls remain reachable without horizontal desktop layouts.

## Testing requirement

A release must fail if a new public CLI command or parameter is not represented in the Workbench schema. The exhaustive contract tests also invoke help for every public command and check that documented CLI options/required arguments remain reachable.

Destructive actions are not executed merely to satisfy test coverage. Their parser, Web representation, classification and approval/policy gates are tested deterministically; actual destructive execution requires explicit human authorization in a suitable test environment.
