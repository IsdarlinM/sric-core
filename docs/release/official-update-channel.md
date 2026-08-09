# Official zero-config update channel

SRIC Core 0.5.5 introduces the default Sentinel Forge update channel used when the user does not pass `--manifest` or `--public-key` and does not configure custom-channel environment variables.

## User contract

```bash
sric update --check
sric update
sric update --force
```

No manifest path or public key is required for the official channel. `--force` reinstalls the selected official release when the available version equals the installed version and still refuses downgrades. `--check` and `--force` are mutually exclusive.

`--manifest` and `--public-key` remain available together as an advanced override for private/custom Ed25519-signed wheel channels. Supplying only one is rejected.

## Trust model

The official channel is registered in SRIC with a fixed `IsdarlinM/<repository>` mapping. The mutable channel document contains only product/version/repository and immutable commit identifiers; it cannot select an arbitrary executable, host, package name, or install command.

Before installation SRIC:

1. validates the channel schema, product and exact official repository;
2. resolves the immutable GitHub commit through the GitHub API;
3. requires GitHub to report the release commit as signature-verified;
4. downloads the source archive for that exact commit;
5. rejects traversal, symlinks, excessive archive sizes and malformed repository roots;
6. reads `pyproject.toml` from the archive and requires exact product and version equality;
7. backs up product state;
8. installs with `python -m pip install --upgrade --no-deps`, adding `--force-reinstall` only for force mode;
9. verifies the installed distribution version;
10. restores the verified rollback snapshot and state if installation fails.

Normal upgrades require channel rollback metadata matching the currently installed version. A forced same-version reinstall uses the same verified target snapshot as its recovery package.

The official updater never executes `git pull`, never accepts HTTP, never invokes a shell, and never lets remote channel metadata choose an executable.

## Custom channels

Custom channels continue to use the original Ed25519 manifest plus SHA-256 wheel contract. These are explicit overrides and do not affect normal users.
