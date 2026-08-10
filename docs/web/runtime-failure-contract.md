# Web runtime failure contract

Sentinel Forge Web surfaces are projections of the installed CLI contract. They are not independent command implementations and they never expose an operating-system shell.

## Required behavior

- Every public CLI command and parameter must be representable by the generated Web catalog.
- Unknown Click/Typer-compatible parameter subclasses are serialized conservatively instead of collapsing the whole interface.
- A missing or malformed operation/control mapping fails the catalog closed with a bounded, redacted HTTP `503`; it must not escape as an ASGI traceback/HTTP `500`.
- Expected user errors keep their normal controlled status (`404`, `409`, `422`, etc.).
- Unexpected submission, job-history, status and cancellation errors return bounded, redacted HTTP `503` responses.
- An unexpected SSE output failure emits a final controlled `failed` event rather than raising out of the streaming generator.
- The browser exposes a real **Reload interface** action and visible catalog-health status. Promise/script errors are surfaced in the existing evidence/output area rather than silently leaving controls empty.
- Web execution remains fixed-runner `shell=False`, no arbitrary executable, no free-form argv UI, CSRF protected, redacted and approval-gated.

## Mutation classification

Commands that can write workspace or output state are conservatively classified as `MUTATING_REVERSIBLE` for Web execution even when their common use may feel read-only. This includes `collect`, `collect-url`, `demo`, `evidence`, `extract`, `report`, `validate`, `notebook`, `jobs`, and `workspace` where applicable. Human approval is required before execution.

## Validation

The release gate must execute the public-command functional smoke plus the Web parameter/exception contract. A hosted job with no allocated runner or no executed steps is not PASS evidence.
