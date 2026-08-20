#!/usr/bin/env bash
# Pulls the centrally configured Canvas course roster and gradebook through the
# guarded local server, then creates private seating/nameplate derivatives.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
cd "$ENGINE"
if [ ! -x "$ENGINE/.venv/bin/python" ]; then
  echo "No environment found. Run setup-after-move.command first."
  read -rp "Press return to close… " _
  exit 1
fi
"$ENGINE/.venv/bin/python" "$ENGINE/scripts/pull_canvas_roster.py" \
  --config "$HERE/pull-canvas-roster.config.jsonc"
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
  NEWEST="$(ls -dt "$ENGINE/out/private-roster"/* 2>/dev/null | head -1)"
  [ -n "$NEWEST" ] && open "$NEWEST" 2>/dev/null || true
else
  echo "Pull failed. Confirm that start-server.command is running for the configured course."
fi
echo; read -rp "Press return to close… " _
exit "$STATUS"
