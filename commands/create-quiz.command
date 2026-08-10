#!/usr/bin/env bash
# Converts a Testmaker-tagged file into a Classic Canvas Quiz. Settings: create-quiz.config.jsonc.
# Requires start-server.command unless dry_run is true.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"
eval "$(read_config "$CONFIG")"

args=( "$ENGINE/.venv/bin/canvas-automation" create-quiz --engine "$ENGINE" --config "$CONFIG" )
[ -n "${1:-}" ] && args+=( --input "$1" )
launch "$OUT_DIR" -- "${args[@]}"

echo; read -rp "Press return to close… " _
