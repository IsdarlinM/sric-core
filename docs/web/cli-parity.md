# Web/CLI capability parity

SRIC Core 0.5.4 provides the shared Web Command Console used by Sentinel Forge products.

## Goal

The Web UI must expose the same public product capabilities as the CLI without implementing a second, drifting business-logic layer and without becoming an operating-system shell.

The console derives its catalog from the installed Typer command tree. A product mounts the shared console with its product identifier, display name, CLI module and version. Commands added to that CLI become visible automatically after the product is upgraded.

## Execution model

The browser submits:

- an exact command path selected from the discovered catalog, such as `workspace list`;
- an argv array for that command;
- explicit approval metadata when required.

The server invokes a fixed process:

```text
python -m sric.web_console_runner <command> <argv...>
```

The product CLI module is configured by the server, not supplied by the browser. `subprocess.Popen` is called with `shell=False`, stdin disabled, a fixed Python executable and the exact argv array. Shell metacharacters therefore remain ordinary CLI arguments and cannot select another executable.

The `web` command is catalogued but marked context-only and cannot be executed from inside the Web server.

## Human control and action classification

The console attaches one of the shared action classes to every command entry:

- `READ_ONLY_SAFE`
- `READ_ONLY_SENSITIVE`
- `MUTATING_REVERSIBLE`
- `MUTATING_DESTRUCTIVE`

Known mutating command names require an explicit approval checkbox. Destructive command names additionally require the exact phrase `APPROVE <command path>`. Product-level Scope Engine, Policy Engine, rate limiting, target validation and command-specific approvals remain authoritative; the Web console does not bypass or replace them.

## Privacy and security

- Each application instance generates an unpredictable anti-CSRF token.
- The token is delivered only in the same-origin console page and is required for job submission and cancellation.
- Console arguments are redacted before they are retained in the in-memory job record.
- Console output passes through SRIC text redaction and ANSI/control-character stripping before browser delivery.
- Jobs are not persisted by the console layer.
- Output retention is capped at 1 MB per job by default.
- Runtime is capped at 30 minutes per job by default.
- Concurrency is capped at two jobs per application instance by default.
- Standard output and standard error are combined and streamed with Server-Sent Events.
- The console UI writes command output with `textContent`; command output is untrusted data, never HTML or instructions.

## API

`GET /console`
: Responsive Web Command Console.

`GET /api/v1/console/catalog`
: Discovered command tree, parameters, action classes and execution limits.

`POST /api/v1/console/jobs`
: Submit one catalogued command. Requires `X-Sentinel-Console-Token`.

`GET /api/v1/console/jobs`
: Current in-memory console job snapshots.

`GET /api/v1/console/jobs/{job_id}`
: One job snapshot.

`GET /api/v1/console/jobs/{job_id}/events`
: SSE output/status stream.

`POST /api/v1/console/jobs/{job_id}/cancel`
: Request process termination. Requires `X-Sentinel-Console-Token`.

## Deliberate limitations

CLI commands that rely on an interactive stdin prompt must be supplied the equivalent explicit CLI flags because Web console subprocess stdin is disabled. This avoids hidden prompts, password capture and hung jobs.

The console does not make a command safe merely because it is reachable from the browser. Active product commands still pass through the same product safety gates as their CLI invocation.
