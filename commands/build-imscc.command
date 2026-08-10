#!/usr/bin/env bash
# Builds a Canvas Common Cartridge for Course Import. Settings: build-imscc.config.jsonc.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME; cd "$ENGINE"; source "$HERE/_lib.sh"
CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"; eval "$(read_config "$CONFIG")"
args=( "$ENGINE/.venv/bin/canvas-automation" build-imscc --engine "$ENGINE" --config "$CONFIG" )
[ -n "${1:-}" ] && args+=( --spec "$1" )
launch "$OUT_DIR" -- "${args[@]}"
echo; read -rp "Press return to close… " _
