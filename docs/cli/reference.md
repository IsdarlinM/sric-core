# CLI Reference — sric v0.3.0

Generated from the registered command surface. Every registered command below uses the same Click/Typer command tree used at runtime.

## Root help

```text
Usage: sric [OPTIONS] COMMAND [ARGS]...

  Security Research Intelligence Core — evidence-native shared primitives.

Options:
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  -h, --help            Show this message and exit.

Commands:
  version       Print the installed SRIC version.
  doctor        Check Python/runtime prerequisites and local configuration.
  query         Search the temporal graph or execute the read-only graph...
  job           List jobs, inspect one job, or request cancellation.
  notebook      List/append research notes or manage saved investigation...
  lineage       Explain evidence lineage from source observations to a...
  import-check  Validate a hostile local import or ZIP before any parser...
  update        Check or install a signed wheel release; never performs a...
  web           Run the local SRIC API.
  help          Show root help or help for a top-level command.
  workspace     Create and inspect isolated research workspaces.
  plugins       Inspect plugin manifests and declared permissions.
  ai            Inspect AI mode.
  scope         Evaluate targets against explicit scope policy.
```

## `sric ai`

```text
Usage: sric ai [OPTIONS] COMMAND [ARGS]...

  Inspect AI mode. AI is disabled by default.

Options:
  -h, --help  Show this message and exit.

Commands:
  status  Show the default AI mode.
  test    Verify that disabled mode fails closed rather than making an...
```

## `sric ai status`

```text
Usage: sric ai status [OPTIONS]

  Show the default AI mode. Cloud AI is never enabled implicitly.

Options:
  -h, --help  Show this message and exit.
```

## `sric ai test`

```text
Usage: sric ai test [OPTIONS]

  Verify that disabled mode fails closed rather than making an external call.

Options:
  -h, --help  Show this message and exit.
```

## `sric doctor`

```text
Usage: sric doctor [OPTIONS]

  Check Python/runtime prerequisites and local configuration.

Options:
  --json      Emit machine-readable JSON.
  -h, --help  Show this message and exit.
```

## `sric help`

```text
Usage: sric help [OPTIONS] [COMMAND]

  Show root help or help for a top-level command.

Arguments:
  [COMMAND]

Options:
  -h, --help  Show this message and exit.
```

## `sric import-check`

```text
Usage: sric import-check [OPTIONS] PATH

  Validate a hostile local import or ZIP before any parser consumes it.

Arguments:
  PATH  [required]

Options:
  -h, --help  Show this message and exit.
```

## `sric job`

```text
Usage: sric job [OPTIONS]

  List jobs, inspect one job, or request cancellation.

Options:
  --workspace DIRECTORY  [required]
  --id TEXT
  --cancel
  -h, --help             Show this message and exit.
```

## `sric lineage`

```text
Usage: sric lineage [OPTIONS] ARTIFACT_ID

  Explain evidence lineage from source observations to a derived artifact.

Arguments:
  ARTIFACT_ID  [required]

Options:
  --workspace DIRECTORY  [required]
  -h, --help             Show this message and exit.
```

## `sric notebook`

```text
Usage: sric notebook [OPTIONS]

  List/append research notes or manage saved investigation queries.

Options:
  --workspace DIRECTORY   [required]
  --type TEXT
  --title TEXT
  --body TEXT
  --status TEXT           [default: OBSERVED]
  --save-query-name TEXT
  --query TEXT
  --list-queries
  -h, --help              Show this message and exit.
```

## `sric plugins`

```text
Usage: sric plugins [OPTIONS] COMMAND [ARGS]...

  Inspect plugin manifests and declared permissions.

Options:
  -h, --help  Show this message and exit.

Commands:
  list     List installed plugin manifests.
  inspect  Show a plugin manifest and declared permissions.
  install  Install a validated plugin manifest only; plugin code is never...
  disable  Disable an installed plugin without deleting its manifest.
  enable   Enable a previously disabled plugin manifest.
  verify   Verify plugin manifest integrity/shape and show declared...
  remove   Remove an installed plugin manifest.
```

## `sric plugins disable`

```text
Usage: sric plugins disable [OPTIONS] NAME

  Disable an installed plugin without deleting its manifest.

Arguments:
  NAME  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins enable`

```text
Usage: sric plugins enable [OPTIONS] NAME

  Enable a previously disabled plugin manifest.

Arguments:
  NAME  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins inspect`

```text
Usage: sric plugins inspect [OPTIONS] NAME

  Show a plugin manifest and declared permissions.

Arguments:
  NAME  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins install`

```text
Usage: sric plugins install [OPTIONS] MANIFEST

  Install a validated plugin manifest only; plugin code is never auto-
  executed.

Arguments:
  MANIFEST  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins list`

```text
Usage: sric plugins list [OPTIONS]

  List installed plugin manifests. Plugin code is not auto-executed.

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins remove`

```text
Usage: sric plugins remove [OPTIONS] NAME

  Remove an installed plugin manifest.

Arguments:
  NAME  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric plugins verify`

```text
Usage: sric plugins verify [OPTIONS] NAME

  Verify plugin manifest integrity/shape and show declared permissions.

Arguments:
  NAME  [required]

Options:
  --path PATH  [default: /home/oai/.sric/plugins]
  -h, --help   Show this message and exit.
```

## `sric query`

```text
Usage: sric query [OPTIONS] QUERY

  Search the temporal graph or execute the read-only graph query DSL.

Arguments:
  QUERY  [required]

Options:
  --workspace DIRECTORY  [required]
  --limit INTEGER RANGE  [default: 50; 1<=x<=500]
  --dsl                  Interpret QUERY as read-only Security Research Graph
                         Query Language.
  -h, --help             Show this message and exit.
```

## `sric scope`

```text
Usage: sric scope [OPTIONS] COMMAND [ARGS]...

  Evaluate targets against explicit scope policy.

Options:
  -h, --help  Show this message and exit.

Commands:
  check  Evaluate a target against an explicit allow/deny scope policy.
```

## `sric scope check`

```text
Usage: sric scope check [OPTIONS] TARGET

  Evaluate a target against an explicit allow/deny scope policy.

Arguments:
  TARGET  [required]

Options:
  --method TEXT  [default: GET]
  --allow TEXT
  --deny TEXT
  -h, --help     Show this message and exit.
```

## `sric update`

```text
Usage: sric update [OPTIONS]

  Check or install a signed wheel release; never performs a blind git pull.

Options:
  --check            Verify release metadata and only report availability.
  --manifest TEXT    Signed release manifest path or HTTPS URL.
  --public-key PATH  Trusted Ed25519 release public key.
  -h, --help         Show this message and exit.
```

## `sric version`

```text
Usage: sric version [OPTIONS]

  Print the installed SRIC version.

Options:
  -h, --help  Show this message and exit.
```

## `sric web`

```text
Usage: sric web [OPTIONS]

  Run the local SRIC API. Non-loopback binding remains rejected until
  authenticated TLS mode is configured.

Options:
  --host TEXT           [default: 127.0.0.1]
  --port INTEGER RANGE  [default: 8765; 1<=x<=65535]
  -h, --help            Show this message and exit.
```

## `sric workspace`

```text
Usage: sric workspace [OPTIONS] COMMAND [ARGS]...

  Create and inspect isolated research workspaces.

Options:
  -h, --help  Show this message and exit.

Commands:
  create  Create an isolated workspace with its own database and evidence...
  list    List local workspaces.
```

## `sric workspace create`

```text
Usage: sric workspace create [OPTIONS] NAME

  Create an isolated workspace with its own database and evidence store.

Arguments:
  NAME  [required]

Options:
  --root PATH  [default: /home/oai/.sric/workspaces]
  -h, --help   Show this message and exit.
```

## `sric workspace list`

```text
Usage: sric workspace list [OPTIONS]

  List local workspaces.

Options:
  --root PATH  [default: /home/oai/.sric/workspaces]
  -h, --help   Show this message and exit.
```
