# First-party runtime compatibility

SRIC Core 0.5.7 introduced the explicit first-party runtime compatibility contract. The current shared Web runtime contract is **SRIC Core >=0.5.11,<0.6**.

## Problem prevented

A product update must not leave a newer product installed beside an older SRIC runtime that lacks modules required by that product. Package metadata alone is not sufficient: a partially replaced or same-version-corrupt runtime can report an acceptable version while a required module is absent.

The 0.5.11 Web Command Console also depends on the JSON-safe command catalog layer. Accepting only `sric.web_console` and `sric.web_workbench` is therefore insufficient for products that expose the shared Console/Workbench.

## Contract

`check_runtime_compatibility()` validates:

- installed first-party distribution version;
- minimum supported version;
- optional exclusive upper bound;
- presence of required runtime modules.

`ensure_official_runtime()` can repair an already-installed first-party runtime only through its fixed Sentinel Forge official repository and the existing GitHub signature-verified update channel. It does not accept an arbitrary package name, executable, install command, or download URL.

For shared Web Console/Workbench generation, downstream products require SRIC Core `>=0.5.11,<0.6` and verify all of:

```text
sric.web_console
sric.web_workbench
sric.web_catalog
```

The package dependency, runtime bootstrap, `doctor`, installer integrity probe and regression tests must declare the same floor. A mismatch between those five surfaces is a release blocker.

## Degraded-install behavior

Downstream products must keep `doctor` and `update` reachable when possible even if a shared UI module is missing. Web mounting should fail gracefully with an actionable compatibility response instead of breaking every CLI command at import time.

A same-version runtime can still be corrupt. Missing required modules must therefore make compatibility fail even when the distribution version is numerically acceptable, and official repair may force reinstall that exact verified version.

## Exception behavior

Compatibility failures are operational errors, not findings. CLI/API/Web surfaces should translate them into concise actionable messages with stable non-zero exit/status behavior. Unexpected exceptions must not expose raw secrets in logs, job records, audit metadata or browser responses.

## Testing

Regression tests must cover:

- an older SRIC runtime;
- required module absence, including `sric.web_catalog`;
- signed-channel upgrade to the current required floor;
- same-version force reinstall for a corrupt runtime;
- rejection of an unsupported newer compatibility range;
- `pip check` after installation;
- clean-install and repair-install smokes;
- HTTP 200 + JSON serialization of the command catalog;
- exact CLI/Web feature and argument parity.

This compatibility check complements, rather than replaces, updater rollback checks, installer preservation tests, security/fuzz tests and exact-commit release evidence.
