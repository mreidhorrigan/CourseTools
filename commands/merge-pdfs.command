#!/usr/bin/env bash
# Opens a native Finder dialog to pick any number of PDFs, then merges
# them into one, in the order you selected them. Settings:
# merge-pdfs.config.jsonc. Purely local; does not need the server running.
#
# Not choose_input: that helper resolves ONE input (a folder or a file)
# three ways (positional/native-picker/config-default). This command's
# whole point is an arbitrary, multi-select list picked fresh each run, so
# it talks to Finder directly via osascript instead. See
# research/00-retrofit-notes.md.
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

SELECTED="$(osascript <<'APPLESCRIPT'
set theFiles to choose file with prompt "Select PDFs to merge (Cmd-click or Shift-click for multiple), in the order you want them combined:" of type {"pdf"} with multiple selections allowed
set posixPaths to {}
repeat with aFile in theFiles
    set end of posixPaths to POSIX path of aFile
end repeat
set text item delimiters of AppleScript to linefeed
return posixPaths as text
APPLESCRIPT
)"
PICKER_STATUS=$?

if [ "$PICKER_STATUS" -ne 0 ] || [ -z "$SELECTED" ]; then
  echo "No files selected."
  read -rp "Press return to close… " _
  exit 0
fi

FILES=()
while IFS= read -r line; do
  [ -n "$line" ] && FILES+=("$line")
done <<< "$SELECTED"

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No files selected."
  read -rp "Press return to close… " _
  exit 0
fi

echo "Selected ${#FILES[@]} file(s)."
launch "$OUT_DIR" -- "$ENGINE/.venv/bin/canvas-automation" merge-pdfs --engine "$ENGINE" --config "$CONFIG" "${FILES[@]}"

echo; read -rp "Press return to close… " _
