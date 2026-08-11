#!/usr/bin/env bash
# skeleton.command — TEMPLATE double-click launcher for ONE tool function.
# Copy this + skeleton.config.jsonc to a new stem (e.g. do-thing.command + do-thing.config.jsonc),
# then edit the line marked EDIT THIS. Settings live in the sibling .config.jsonc.
#
#   • DOUBLE-CLICK in Finder   → asks where the input is (pick a folder, the config's
#                                DEFAULT_INPUT, or its CONFIG_INPUT), then runs.
#   • From a shell / local AI  → ./do-thing.command /path/to/input [KEY=VALUE ...]
#                                A path skips the menu. KEY=VALUE lines override config keys.
#
# See 03-command-and-config.md for the full anatomy (the dual interface + 3-way input choice).
set -uo pipefail

# Resolve this launcher's own dir, so a Finder double-click (any cwd) still finds its siblings.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# ENGINE = the project root that holds .venv and src/. Adjust ".." if commands/ is nested deeper.
ENGINE="$(cd "$HERE/.." && pwd)"

# Shared read_config() + choose_input() + launch() helpers.
source "$HERE/_lib.sh"

# Load the sibling config (same stem as this script) as shell vars.
CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"
eval "$(read_config "$CONFIG")"

# Sort the arguments: the first non-KEY=VALUE arg is the input path; KEY=VALUE lines override
# config keys (handy for shells / local AIs). Either order works.
ARG_INPUT=""
for kv in "$@"; do
  case "$kv" in
    *=*) export "${kv?}" ;;
    *)   [ -z "$ARG_INPUT" ] && ARG_INPUT="$kv" ;;
  esac
done

# Resolve the ONE input to work on. A path argument wins and skips the menu (the dual interface).
# A bare double-click gets the 3-way choice. Cancelling exits cleanly.
INPUT="$(choose_input "$ARG_INPUT")" || { echo "Nothing to do."; echo; read -rp "Press return to close… " _; exit 0; }

# --- EDIT THIS: map the input + config keys to your engine's CLI ------------------
# $INPUT is the resolved input. A generate-from-config tool (no input to pick) drops the
# choose_input line above and reads its own key, like generate-image in 03-command-and-config.md.
args=( "$ENGINE/.venv/bin/TOOL" SUBCOMMAND "$INPUT" --seed "${SEED:-7}" )
[ -n "${NAME:-}" ] && args+=( --name "$NAME" )
# ---------------------------------------------------------------------------------

# Run it, stream output, open the newest item in OUT_DIR, report the exit code.
launch "${OUT_DIR:?set OUT_DIR in the .config.jsonc}" -- "${args[@]}"

echo; read -rp "Press return to close… " _
