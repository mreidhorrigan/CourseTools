#!/usr/bin/env bash
# Prepares the original nameplate tool and, when configured, builds an exact
# DOC_TOOLS seating chart from the newest private roster pull.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"; cd "$ENGINE"
RUN_DIR="${1:-}"
ARGS=(--config "$HERE/build-roster-documents.config.jsonc")
[ -n "$RUN_DIR" ] && ARGS=("$RUN_DIR" "${ARGS[@]}")
"$ENGINE/.venv/bin/python" "$ENGINE/scripts/build_roster_documents.py" "${ARGS[@]}"
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
  TARGET="${RUN_DIR:-$(ls -dt "$ENGINE/out/private-roster"/* 2>/dev/null | head -1)}/documents"
  NAMEPLATES="$TARGET/nameplates-workspace/Nameplates.html"
  if [ -f "$NAMEPLATES" ]; then
    open "$NAMEPLATES" 2>/dev/null || true
  else
    open "$TARGET" 2>/dev/null || true
  fi
fi
echo; read -rp "Press return to close… " _
exit "$STATUS"
