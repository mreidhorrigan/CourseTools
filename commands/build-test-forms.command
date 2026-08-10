#!/usr/bin/env bash
# Builds deterministic PDF forms and answer keys from Testmaker source.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME; cd "$ENGINE"; source "$HERE/_lib.sh"
CONFIG="$HERE/build-test-forms.config.jsonc"; eval "$(read_config "$CONFIG")"
ARGS=(build-test-forms --engine "$ENGINE" --config "$CONFIG")
[ -n "${1:-}" ] && ARGS+=(--input "$1")
launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" "${ARGS[@]}"
echo; read -rp "Press return to close… " _
