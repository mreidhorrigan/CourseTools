#!/usr/bin/env bash
# Converts a Canvas gradebook CSV into a headerless registrar-upload CSV.
# Purely local; does not require the Canvas server.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
cd "$ENGINE"

if [ ! -x "$ENGINE/.venv/bin/python" ]; then
  echo "No environment found. Run setup-after-move.command first."
  read -rp "Press return to close… " _
  exit 1
fi

INPUT="${1:-}"
ARGUMENT_INPUT=false
if [ -n "$INPUT" ]; then ARGUMENT_INPUT=true; fi
if [ -z "$INPUT" ]; then
  INPUT="$(osascript -e 'try' -e 'POSIX path of (choose file with prompt "Choose a Canvas gradebook CSV" of type {"public.comma-separated-values-text", "csv"})' -e 'on error' -e 'return ""' -e 'end try' 2>/dev/null)"
fi
if [ -z "$INPUT" ]; then
  echo "No file selected."
  exit 0
fi

ARGS=("$INPUT" --config "$HERE/convert-gradebook.config.jsonc")
if [ "$ARGUMENT_INPUT" = false ]; then
  OUT="$ENGINE/out/grade-submission/latest"
  mkdir -p "$OUT"
  ARGS+=(--output "$OUT")
else
  OUT="$(cd "$(dirname "$INPUT")" && pwd)"
fi
"$ENGINE/.venv/bin/python" "$ENGINE/scripts/convert_canvas_gradebook.py" "${ARGS[@]}"
STATUS=$?
if [ "$STATUS" -eq 0 ]; then
  echo "Output: $OUT"
  open "$OUT" 2>/dev/null || true
else
  echo "Conversion failed. The source gradebook was not modified."
fi
echo; read -rp "Press return to close… " _
exit "$STATUS"
