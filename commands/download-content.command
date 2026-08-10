#!/usr/bin/env bash
# Downloads existing Canvas content into out/. Settings: download-content.config.jsonc.
# Requires start-server.command to already be running.
#
# Generate-from-config tool, so no choose_input here. See 03-command-and-config.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"
eval "$(read_config "$CONFIG")"

launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" download-content --engine "$ENGINE" --config "$CONFIG"

echo; read -rp "Press return to close… " _
