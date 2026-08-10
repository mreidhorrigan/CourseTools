#!/usr/bin/env bash
# Prompts for a Canvas course URL, then: (1) downloads every published
# assignment and combines them into one PDF, and (2) builds a gradebook
# CSV (and XLSX) for that course. Settings: export-course-packet.config.jsonc.
# Requires start-server.command to already be running.
#
# The course URL is asked for here rather than read from the config,
# unlike every other create-*/download-* command: this one is meant to be
# pointed at a different course each run. See research/00-retrofit-notes.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

if [ ! -x "$ENGINE/.venv/bin/canvas-automation" ]; then
  echo "No environment found. Run setup-after-move.command first (it runs uv sync)."
  read -rp "Press return to close… " _
  exit 1
fi

CONFIG="$HERE/$(basename "${BASH_SOURCE[0]}" .command).config.jsonc"
eval "$(read_config "$CONFIG")"
if [ -n "${__CONFIG_ERROR__:-}" ]; then
  echo "❌ $__CONFIG_ERROR__"
  read -rp "Press return to close… " _
  exit 1
fi

echo "Canvas course URL (e.g. https://yourschool.instructure.com/courses/12345):"
read -r COURSE_URL
if [ -z "$COURSE_URL" ]; then
  echo "A course URL is required."
  read -rp "Press return to close… " _
  exit 1
fi

launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" export-course-packet --engine "$ENGINE" --config "$CONFIG" --course-url "$COURSE_URL"

echo; read -rp "Press return to close… " _
