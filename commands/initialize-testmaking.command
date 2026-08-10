#!/usr/bin/env bash
# Creates or deliberately replaces the private assessment baseline from guarded Canvas.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"; cd "$ENGINE"
PY=".venv/bin/python"; [ -x "$PY" ] || PY="python3"
echo "This reads quiz questions and answers from the guarded Canvas course into private/testmaking/."
echo "That directory is excluded from collaborator distributions and Canvas-hosted toolkit archives."
"$PY" scripts/testmaking_authoring.py export-live --initialize
RC=$?; [ -t 0 ] && { echo; read -rp "Press return to close… " _; }; exit "$RC"
