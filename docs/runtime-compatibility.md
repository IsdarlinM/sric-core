# First-party runtime compatibility

SRIC Core 0.5.7 adds an explicit runtime compatibility contract for Sentinel Forge products.

## Problem prevented

A product update must not leave a newer product installed beside an older SRIC runtime that lacks modules required by that product. Package metadata alone is not sufficient: a partially replaced or same-version-corrupt runtime can report an acceptable version while a required module is absent.

## Contract

`check_runtime_compatibility()` validates:

- installed first-party distribution version;
- minimum supported version;
- optional exclusive upper bound;
- presence of required runtime modules.

`ensure_official_runtime()` can repair an already-installed first-party runtime only through its fixed Sentinel Forge official repository and the existing GitHub signature-verified update channel. It does not accept an arbitrary package name, executable, install command, or download URL.

For the Web Feature Workbench generation, downstream products require SRIC Core >=0.5.7,<0.6 and verify `sric.web_console` plus `sric.web_workbench` before relying on the shared Web surfaces.

## Degraded-install behavior

Downstream products must keep `doctor` and `update` reachable when possible even if an optional/new shared UI module is missing. Web mounting should fail gracefully with an actionable compatibility response instead of breaking every CLI command at import time.

## Testing

Regression tests cover:

- an older SRIC runtime;
- required module absence;
- signed-channel upgrade to the required floor;
- same-version force reinstall for a corrupt runtime;
- rejection of an unsupported newer major/minor compatibility range.

This compatibility check complements, rather than replaces, `pip check`, clean-install smoke tests, updater rollback checks and exact CLI/Web feature parity tests.
