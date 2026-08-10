#!/usr/bin/env bash
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"; cd "$ENGINE"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
"$PY" scripts/testmaking_authoring.py build-pdf
RC=$?; [ -t 0 ] && { echo; read -rp "Press return to close… " _; }; exit "$RC"
