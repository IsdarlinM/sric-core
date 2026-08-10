# Guided Web Security Console

SRIC Core 0.5.13 turns the shared Web Feature Workbench into the primary guided security console for Sentinel Forge products.

## UX contract

The Web UI is an operation-oriented interface, not a terminal or CLI command composer. Users select a capability and configure it through typed HTML controls. They never need to type command paths, option names, flags, or a free-form argv string.

The installed Typer tree remains the canonical capability source so Web and CLI behavior cannot silently diverge. `build_feature_catalog()` derives one Web operation for every public CLI command and preserves parameter order and semantics. The schema carries positional/optional status, multiplicity, arity, defaults, type metadata, help, sensitivity, numeric bounds, path metadata, and closed choice sets.

Controls are selected from that metadata:

- boolean capabilities use checkboxes or explicit Default / Enabled / Disabled selects;
- closed choice sets use select or multi-select controls;
- numeric values use number controls and available bounds;
- repeated values use list/multi-value controls;
- local paths use path-oriented value fields;
- sensitive values use password-style controls;
- optional settings require an explicit `Customize this setting` checkbox before they are serialized.

`feature_contract()` still compares the CLI tree with the Web tree. A complete contract requires identical public operation paths and ordered parameters, with no invented Web-only capability and no CLI-only capability omitted from the UI.

## Routes

- `/workbench` — primary guided, responsive Security Console;
- `/api/v1/workbench/catalog` — typed operation schema and parity contract;
- `/api/v1/workbench/coverage` — machine-readable coverage status;
- `/api/v1/console/jobs` and related job routes — internal execution transport used by the guided UI.

The browser does not expose a free-form arguments field. Internally, structured values are deterministically translated to an argv array and passed to the fixed product runner. This preserves one implementation of product behavior and keeps Scope Engine, Policy Engine, rate limits, approval gates, redaction, audit, and evidence controls authoritative.

## Human control

Mutating operations expose an explicit approval checkbox. Destructive operations require a second destructive-impact acknowledgement. The browser derives the backend approval token only after those controls are selected; users are never asked to memorize or type a CLI approval phrase.

This preserves the project rule: **AI proposes. Evidence proves. Humans control.**

## Security properties

The Security Console:

- does not expose an operating-system shell;
- cannot select an executable;
- exposes no free-form argv/command input;
- uses the fixed `sric.web_console_runner` path with `shell=False`;
- disables stdin;
- reuses the per-process Web CSRF token for mutating requests;
- preserves explicit human approval for mutating/destructive operations;
- treats secret-like inputs as sensitive and keeps shared redaction before retention;
- consumes same-origin assets/APIs under the restrictive CSP;
- streams bounded job state and output through the existing SSE mechanism;
- treats imported/external content as untrusted data, never browser instructions.

## Responsive behavior

Desktop presents Operations, Configure, and Recent Activity panels. Small screens switch between those sections using large touch-friendly buttons. Every public operation remains reachable without horizontal desktop layouts or memorized syntax.

## Testing requirement

A release must fail if a public CLI command or parameter is missing from the structured Web catalog. Tests also fail if the primary Workbench reintroduces `Advanced argv`, `Additional arguments`, or another free-form command-syntax field.

Destructive actions are not executed merely to satisfy test coverage. Their representation, classification, approval/policy gates, and deterministic serialization are tested without performing destructive work.