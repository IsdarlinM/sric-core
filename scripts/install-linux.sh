#!/usr/bin/env sh
set -eu

PROJECT="SRIC Core"
CMD="sric"
INSTALL_ROOT="${HOME}/.local/share/sric"
VENV="$INSTALL_ROOT/venv"
SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
CONSTRAINTS="$REPO_ROOT/requirements/runtime-py311.lock"
FIRST_PARTY="$REPO_ROOT/requirements/first-party.txt"

if [ "$(id -u)" = "0" ] && [ "${ALLOW_ROOT_INSTALL:-0}" != "1" ]; then
  echo "Refusing root install by default. Run as your normal user or set ALLOW_ROOT_INSTALL=1 intentionally." >&2
  exit 2
fi

if [ -n "${PYTHON:-}" ]; then
  command -v "$PYTHON" >/dev/null 2>&1 || { echo "Configured PYTHON executable was not found: $PYTHON" >&2; exit 2; }
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3.11+ is required." >&2
  exit 2
fi
"$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1 || {
  echo "Python 3.11+ is required." >&2
  exit 2
}

BIN_DIR="${HOME}/.local/bin"
if [ -n "${PREFIX:-}" ] && [ -d "${PREFIX}/bin" ] && [ -w "${PREFIX}/bin" ]; then
  case ":${PATH:-}:" in
    *":${PREFIX}/bin:"*) BIN_DIR="${PREFIX}/bin" ;;
  esac
fi
mkdir -p "$INSTALL_ROOT" "$BIN_DIR"

if [ -x "$VENV/bin/python" ]; then
  if ! "$VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)' >/dev/null 2>&1; then
    echo "Rebuilding obsolete or broken runtime environment: $VENV"
    rm -rf "$VENV"
  fi
elif [ -e "$VENV" ]; then
  echo "Rebuilding incomplete runtime environment: $VENV"
  rm -rf "$VENV"
fi
if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -m venv "$VENV" || { echo "Failed to create isolated Python environment." >&2; exit 3; }
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
"$VENV/bin/python" -c 'import sric; import sric.web_console; import sric.web_workbench; import sric.web_catalog' || {
  echo "SRIC Core import integrity check failed." >&2
  exit 3
}

ln -sfn "$VENV/bin/$CMD" "$BIN_DIR/$CMD"

case ":${PATH:-}:" in
  *":$BIN_DIR:"*) ;;
  *)
    PROFILE="${HOME}/.profile"
    PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'
    touch "$PROFILE"
    if ! grep -F "$PATH_LINE" "$PROFILE" >/dev/null 2>&1; then
      printf '\n# Security Research Intelligence tools\n%s\n' "$PATH_LINE" >> "$PROFILE"
    fi
    printf 'PATH is configured for new login shells via %s.\n' "$PROFILE"
    ;;
esac

CHECK_LOG="$INSTALL_ROOT/install-check.log"
: > "$CHECK_LOG"
run_check() {
  label="$1"
  shift
  if ! SENTINEL_BANNER=never "$@" >>"$CHECK_LOG" 2>&1; then
    printf 'Installation validation failed: %s\n' "$label" >&2
    cat "$CHECK_LOG" >&2
    exit 4
  fi
}
run_check doctor "$VENV/bin/$CMD" doctor
run_check capabilities "$VENV/bin/$CMD" capabilities
run_check help "$VENV/bin/$CMD" --help
run_check short-help "$VENV/bin/$CMD" -h
run_check help-alias "$VENV/bin/$CMD" help
rm -f "$CHECK_LOG"
printf '%s installed/repaired successfully.\n' "$PROJECT"
printf 'Command: %s\n' "$CMD"