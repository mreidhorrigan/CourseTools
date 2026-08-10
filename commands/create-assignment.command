#!/usr/bin/env bash
# Creates a Canvas assignment. Settings: create-assignment.config.jsonc.
# Requires start-server.command to already be running.
#
# Generate-from-config tool (its subject is named in the config, not
# picked from a folder), so no choose_input here. See 03-command-and-config.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"
eval "$(read_config "$CONFIG")"

launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" create-assignment --engine "$ENGINE" --config "$CONFIG"

echo; read -rp "Press return to close… " _
