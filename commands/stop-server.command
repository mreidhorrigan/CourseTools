#!/usr/bin/env bash
# Asks the running server to shut down over HTTP. Ctrl+C (or closing) the
# start-server.command window does the same thing directly; this is only
# for when that window is not handy.
#
# No dedicated stop-server.config.jsonc: this command has no settings of
# its own, only the host/port the running server is already using, so it
# reads start-server.config.jsonc directly rather than duplicating those
# two values into a second file that would just need to stay in sync.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

if [ -x "$ENGINE/.venv/bin/canvas-automation" ]; then
  "$ENGINE/.venv/bin/canvas-automation" stop --engine "$ENGINE"
else
  echo "No environment found. Run setup-after-move.command first (it runs uv sync)."
fi

echo
read -rp "Press return to close… " _
