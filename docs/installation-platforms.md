# Installation and uninstallation

SRIC Core provides explicit lifecycle scripts for both supported desktop/server families.

| Platform | Install | Uninstall |
|---|---|---|
| Linux / Termux | `sh scripts/install-linux.sh` | `sh scripts/uninstall-linux.sh` |
| Windows | `scripts\install-windows.cmd` | `scripts\uninstall-windows.cmd` |

The Windows uninstaller removes the `sric.cmd` shim and isolated runtime venv, but does not remove the shared `%USERPROFILE%\.local\bin` PATH entry because sibling Sentinel Forge tools can use it. Configuration, workspaces, plugins and evidence are preserved by default.

The Linux uninstaller follows the same data-preservation principle. Destructive user-data removal is intentionally not part of the default uninstall path.
