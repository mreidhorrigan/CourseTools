#!/usr/bin/env bash
# Initialize one target course from a pasted browser URL; no token is requested or stored.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
cd "$ENGINE"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" scripts/initialize_toolkit.py
RC=$?
echo
[ "$RC" -eq 0 ] && echo "✓ Initialization saved. Open course/course.config.jsonc to review it." || echo "✗ Initialization failed."
[ -t 0 ] && read -rp "Press return to close… " _
exit "$RC"
