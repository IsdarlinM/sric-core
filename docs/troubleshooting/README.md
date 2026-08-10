# Troubleshooting

Start with:

```bash
sric doctor --json
sric capabilities
```

## Unexpected CLI failures

Sentinel Forge CLI entrypoints contain unexpected application exceptions at the shared SRIC presentation boundary. Normal commands should return a concise redacted error and a non-zero exit code instead of emitting a Python traceback. `KeyboardInterrupt` maps to exit code 130.

For local developer diagnostics only, set `SENTINEL_DEBUG=1` before reproducing the problem. Raw debug tracebacks may contain sensitive application data, so do not paste them into issues or reports without reviewing and redacting them first.

## Web Command Console catalog failures

A healthy SRIC 0.5.11+ runtime exposes `sric.web_console`, `sric.web_workbench` and `sric.web_catalog`. Product installers pin an immutable compatible SRIC source and validate these imports before reporting success. If `/console` reports that the command catalog cannot be loaded, run the product's `doctor --json` first and then rerun that product's installer rather than deleting the product home directory.

Installer-internal doctor/capability/help smokes set `SENTINEL_BANNER=never`, capture diagnostics, and only print the captured log when a validation step fails. Repeated banners during a successful install indicate an older installer/runtime pair.

## PATH

For PATH issues, confirm `~/.local/bin` on standard Linux or `%LOCALAPPDATA%\SRIC\bin` on Windows is present in a newly opened shell. Termux-capable product installers prefer a writable `$PREFIX/bin` that is already on `PATH`.

## Web/API binding

SRIC intentionally rejects non-loopback Web/API binding until authenticated TLS mode is implemented. Use `127.0.0.1`, `localhost` or `::1` for the local UI/API.

## Error and audit privacy

Operational exception text and audit metadata must be redacted before persistence or display. Do not place passwords, session cookies, bearer tokens, API keys or private keys in command arguments, issue text or debug logs. If a secret appears in an error path, treat it as exposed and rotate it according to the relevant system policy.
