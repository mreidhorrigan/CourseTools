#!/usr/bin/env bash
# Simulates assignment completion and rubric grading through Mistral.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME; cd "$ENGINE"; source "$HERE/_lib.sh"
CONFIG="$HERE/test-assignment-rubric.config.jsonc"; eval "$(read_config "$CONFIG")"
launch "$OUT_DIR" -- "$ENGINE/.venv/bin/python" scripts/mistral_assignment_qa.py --root "$ENGINE" --config "$CONFIG"
echo; read -rp "Press return to close… " _
