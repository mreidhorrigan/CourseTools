#!/usr/bin/env bash
# Derives the Canvas domain from sandbox_course_url, prompts for the API token,
# then starts the local server
# (canvas-automation serve). Settings: start-server.config.jsonc (holds no
# credentials; see the note at the top of that file). Leave this window
# open while using the other commands/*.command files. Ctrl+C, or closing
# this window, stops the server; stop-server.command is a remote way to do
# the same thing if this window is out of reach.
#
# This is the one interactive step in the whole tool, by design: the engine
# in src/ takes no interactive input at all (see 02-project-structure.md's
# engine/interface split), and normal launch()-style output-opening does
# not fit a long-running server, so this script talks to _lib.sh only for
# read_config, not for launch. See research/canvas-api-endpoints.md for why.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME
cd "$ENGINE"
source "$HERE/_lib.sh"

if [ ! -x "$ENGINE/.venv/bin/canvas-automation" ]; then
  echo "No environment found."
  echo "Run setup-after-move.command first (it runs uv sync)."
  echo
  read -rp "Press return to close… " _
  exit 1
fi

eval "$(read_config "$HERE/start-server.config.jsonc")"
if [ -n "${__CONFIG_ERROR__:-}" ]; then
  echo "❌ $__CONFIG_ERROR__"
  read -rp "Press return to close… " _
  exit 1
fi

CANVAS_BASE_URL="${sandbox_course_url%%/courses/*}"
ALLOWED_COURSE_ID="${sandbox_course_url#*/courses/}"
ALLOWED_COURSE_ID="${ALLOWED_COURSE_ID%%[/?#]*}"
if [ -z "$CANVAS_BASE_URL" ] || [ "$CANVAS_BASE_URL" = "$sandbox_course_url" ]; then
  echo "❌ Could not derive a Canvas base URL from sandbox_course_url: $sandbox_course_url"
  read -rp "Press return to close… " _
  exit 1
fi
if ! [[ "$ALLOWED_COURSE_ID" =~ ^[0-9]+$ ]]; then
  echo "❌ Could not derive a numeric course ID from sandbox_course_url: $sandbox_course_url"
  read -rp "Press return to close… " _
  exit 1
fi

# Make double-click startup idempotent. Check the configured loopback port before asking the
# operator to enter a token, and distinguish our matching server from an unrelated process.
PROBE_OUTPUT="$("$ENGINE/.venv/bin/python" "$ENGINE/scripts/check_running_server.py" \
  --host "$host" --port "$port" --course-id "$ALLOWED_COURSE_ID" \
  --canvas-base-url "$CANVAS_BASE_URL" 2>&1)"
PROBE_RC=$?
if [ "$PROBE_RC" -eq 0 ]; then
  echo "$PROBE_OUTPUT"
  echo "No token entry or second server is needed. Leave the original server window open."
  read -rp "Press return to close this duplicate window… " _
  exit 0
elif [ "$PROBE_RC" -ne 3 ]; then
  echo "❌ $PROBE_OUTPUT"
  echo "Stop the process using port $port, or choose another port in start-server.config.jsonc."
  read -rp "Press return to close… " _
  exit 1
fi

echo "Canvas sandbox: $sandbox_course_url"
echo "Canvas API host: $CANVAS_BASE_URL"
echo "Canvas API token (input hidden as you type):"
read -rs CANVAS_API_TOKEN
echo
echo

if [ -z "$CANVAS_API_TOKEN" ]; then
  echo "An API token is required."
  read -rp "Press return to close… " _
  exit 1
fi

export CANVAS_BASE_URL CANVAS_API_TOKEN
echo "Starting the server. Leave this window open; press Ctrl+C here to stop it."
echo

"$ENGINE/.venv/bin/canvas-automation" serve --engine "$ENGINE"
RC=$?
unset CANVAS_API_TOKEN CANVAS_BASE_URL

echo
if [ "$RC" -eq 0 ] || [ "$RC" -eq 130 ]; then
  echo "✓ Server stopped."
else
  echo "❌ The server exited with an error (exit $RC). Check the messages above."
fi
read -rp "Press return to close… " _
