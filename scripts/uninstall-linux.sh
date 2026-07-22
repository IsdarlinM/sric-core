#!/usr/bin/env sh
set -eu
rm -f "${HOME}/.local/bin/sric"
rm -rf "${HOME}/.local/share/sric"
echo "SRIC runtime removed. User workspaces under ~/.sric were preserved."
