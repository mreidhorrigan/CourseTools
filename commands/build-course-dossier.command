#!/usr/bin/env bash
# Builds a bookmarked, continuously numbered course-design PDF from the local
# canonical course sources selected in build-course-dossier.config.jsonc.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"
CONFIG="$HERE/build-course-dossier.config.jsonc"
if [ ! -x "$ENGINE/.venv/bin/python" ]; then echo "Run setup-after-move.command first."; read -rp "Press return to close… " _; exit 1; fi
"$ENGINE/.venv/bin/python" "$ENGINE/scripts/build_course_dossier.py" --config "$CONFIG"
status=$?
echo; read -rp "Press return to close… " _
exit $status
