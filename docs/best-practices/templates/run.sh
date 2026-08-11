#!/usr/bin/env sh
# run.sh — the PORTABLE contract. POSIX sh, no macOS-only calls, so a Linux user (or CI, or a
# container) runs THIS, while a macOS user double-clicks the .command. Both hit one code path.
# See 06-vendoring-and-linking.md and 11-suites-and-sharing.md.
#
#   sh run.sh do-thing [KEY=VALUE ...]      # or: ./run.sh do-thing
#
# The macOS .command can delegate its core to this script so logic never forks across OSes.
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
ENGINE="$HERE"
PY="$ENGINE/.venv/bin/python"; [ -x "$PY" ] || PY="python3"

FUNC="${1:-do-thing}"; [ "$#" -gt 0 ] && shift || true
CONFIG="$ENGINE/commands/$FUNC.config.jsonc"
[ -f "$CONFIG" ] || CONFIG="$ENGINE/$FUNC.config.jsonc"

# Load config as shell vars (string-aware, schema-validated; errors surface as __CONFIG_ERROR__).
eval "$("$PY" "$ENGINE/commands/_jsonc.py" "$CONFIG" 2>/dev/null || "$PY" "$ENGINE/_jsonc.py" "$CONFIG")"
if [ -n "${__CONFIG_ERROR__:-}" ]; then
  echo "config error: $__CONFIG_ERROR__" >&2
  exit 1
fi

# Optional KEY=VALUE overrides for scripts / agents.
for kv in "$@"; do
  case "$kv" in *=*) export "$kv" ;; esac
done

mkdir -p "${OUT_DIR:?set OUT_DIR in the config}"
# EDIT THIS: invoke your engine. Keep it POSIX and AI-free.
exec "$PY" -m "${ENGINE_MODULE:-TOOL_NAME}" "$FUNC" --config "$CONFIG"
