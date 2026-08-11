#!/usr/bin/env bash
# verify.command — the network-free gate. Double-click or run before committing.
# Runs: (1) the test suite, (2) a determinism / double-render equality check, (3) config-schema
# validation. Exits non-zero on any failure. Wire it into a pre-commit hook so a red tree cannot
# be committed. See checklist.md and 12-adopting-in-existing-projects.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY="${PYTHON:-.venv/bin/python}"; [ -x "$PY" ] || PY="python3"
fail=0

echo "== 1. tests =="
if "$PY" -c "import pytest" >/dev/null 2>&1 && ls tests/*.py test_*.py >/dev/null 2>&1; then
  "$PY" -m pytest -q || fail=1
else
  echo "   (no pytest suite found; skipping)"
fi

echo "== 2. determinism (double render -> hash equality) =="
# EDIT THIS: render the same config twice into two temp dirs and compare hashes. Stub passes
# until you wire your engine. The contract: same config + same seed => byte-identical output.
#   a="$(mktemp -d)"; b="$(mktemp -d)"
#   OUT_DIR="$a" .venv/bin/TOOL do-thing --config commands/do-thing.config.jsonc
#   OUT_DIR="$b" .venv/bin/TOOL do-thing --config commands/do-thing.config.jsonc
#   ha=$(find "$a" -type f ! -name provenance.json -exec shasum {} \; | awk '{print $1}' | sort | shasum)
#   hb=$(find "$b" -type f ! -name provenance.json -exec shasum {} \; | awk '{print $1}' | sort | shasum)
#   [ "$ha" = "$hb" ] || { echo "   DRIFT: outputs differ"; fail=1; }
echo "   (stub: wire your engine's double-render check here)"

echo "== 3. config-schema validation =="
shopt -s nullglob
for cfg in commands/*.config.jsonc *.config.jsonc; do
  out="$("$PY" commands/_jsonc.py "$cfg" 2>/dev/null || "$PY" _jsonc.py "$cfg" 2>/dev/null)"
  if printf '%s' "$out" | grep -q '__CONFIG_ERROR__'; then
    echo "   INVALID $cfg: ${out#__CONFIG_ERROR__=}"; fail=1
  else
    echo "   ok $cfg"
  fi
done

echo
if [ "$fail" -eq 0 ]; then echo "✓ verify passed"; else echo "✗ verify FAILED"; fi
# Hold the window only on an interactive double-click, not in a hook/CI.
[ -t 0 ] && { echo; read -rp "Press return to close… " _; }
exit "$fail"
