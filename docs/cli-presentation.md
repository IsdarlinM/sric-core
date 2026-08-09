# CLI presentation contract

Sentinel Forge CLIs use a shared SRIC presentation layer. Interactive console entrypoints render a compact ASCII banner in this canonical order: `Tool :: vX.X.X`, `Developer: IsdarlinM`, then the concise product description.

The banner uses a subdued green ANSI style and is written to stderr only when running on an interactive terminal. Redirected stdout, JSON output, exports, evidence, and API payloads remain free of presentation escape sequences.

Use `--no-color` to disable terminal colors while keeping the banner and command behavior intact. The entrypoint normalizes the flag as a global option, so `tool --no-color COMMAND` and `tool COMMAND --no-color` are equivalent when invoked through the installed console script. The standard `NO_COLOR` environment variable is also honored.

The public help contract is mandatory: `tool --help`, `tool -h`, `tool help`, `tool COMMAND --help`, `tool COMMAND -h`, and `tool COMMAND help` must resolve to the same Typer command tree. SRIC 0.5.8 adds explicit root-help alias normalization and an exhaustive regression that walks every public command.

Command/help rendering uses Typer/Rich presentation when color is enabled. This affects human-facing terminal help only; it does not alter stored evidence or machine-readable command results.
