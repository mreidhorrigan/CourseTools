#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"; cd "$ENGINE"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" scripts/course_authoring.py verify
RC=$?
if [ "$RC" -eq 0 ]; then
  if [ -f private/testmaking/testmaking-manifest.json ]; then
    "$PY" scripts/testmaking_authoring.py verify; RC=$?
  else
    echo "Private testmaking baseline not initialized; skipping assessment verification."
    echo "Run commands/initialize-testmaking.command after connecting the guarded server."
  fi
fi
[ -t 0 ] && { echo; read -rp "Press return to close… " _; }; exit "$RC"
