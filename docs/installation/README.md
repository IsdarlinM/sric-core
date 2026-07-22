# Installation

Development: create a Python 3.11+ virtual environment and install `-e '.[dev]'`.

Linux: `./scripts/install-linux.sh`; this creates an isolated environment under `~/.local/share/sric` and a launcher under `~/.local/bin`. `uninstall-linux.sh` preserves `~/.sric` workspaces.

Windows: run `scripts\install-windows.cmd`, then open a new terminal and run `sric doctor`.
