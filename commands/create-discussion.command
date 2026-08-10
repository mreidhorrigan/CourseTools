#!/usr/bin/env bash
# Creates a Canvas discussion topic. Settings: create-discussion.config.jsonc.
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

launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" create-discussion --engine "$ENGINE" --config "$CONFIG"

echo; read -rp "Press return to close… " _
