#!/usr/bin/env sh
set -eu

PROJECT="SRIC Core"
CMD="sric"
INSTALL_ROOT="${HOME}/.local/share/sric"
VENV="$INSTALL_ROOT/venv"
BIN_DIR="${HOME}/.local/bin"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CONSTRAINTS="$REPO_ROOT/requirements/runtime-py311.lock"
FIRST_PARTY="$REPO_ROOT/requirements/first-party.txt"

if [ "$(id -u)" = "0" ] && [ "${ALLOW_ROOT_INSTALL:-0}" != "1" ]; then
  echo "Refusing root install by default. Run as your normal user or set ALLOW_ROOT_INSTALL=1 intentionally." >&2
  exit 2
fi

PYTHON="${PYTHON:-python3}"
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1 || {
  echo "Python 3.11+ is required." >&2
  exit 2
}

mkdir -p "$INSTALL_ROOT" "$BIN_DIR"
if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip setuptools wheel || {
  echo "Failed to bootstrap pip/setuptools/wheel." >&2
  exit 3
}

if [ -f "$FIRST_PARTY" ]; then
  "$VENV/bin/python" -m pip install --upgrade -c "$CONSTRAINTS" -r "$FIRST_PARTY" || {
    echo "Failed to install Sentinel Forge first-party dependencies." >&2
    exit 3
  }
fi

"$VENV/bin/python" -m pip install --upgrade -c "$CONSTRAINTS" "$REPO_ROOT" || {
  echo "Failed to install SRIC Core runtime." >&2
  exit 3
}
"$VENV/bin/python" -m pip check || {
  echo "Installed dependency graph is inconsistent." >&2
  exit 3
}
"$VENV/bin/python" -c 'import sric; import sric.web_console; import sric.web_workbench' || {
  echo "SRIC Core import integrity check failed." >&2
  exit 3
}

ln -sfn "$VENV/bin/$CMD" "$BIN_DIR/$CMD"

PROFILE="${HOME}/.profile"
PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
touch "$PROFILE"
if ! grep -F "$PATH_LINE" "$PROFILE" >/dev/null 2>&1; then
  printf '\n# Security Research Intelligence tools\n%s\n' "$PATH_LINE" >> "$PROFILE"
fi

"$VENV/bin/$CMD" doctor
"$VENV/bin/$CMD" capabilities
"$VENV/bin/$CMD" --help >/dev/null
"$VENV/bin/$CMD" -h >/dev/null
"$VENV/bin/$CMD" help >/dev/null
printf '%s installed/repaired successfully.\n' "$PROJECT"
printf 'Command: %s\n' "$CMD"
printf 'PATH is configured for new login shells via %s.\n' "$PROFILE"
