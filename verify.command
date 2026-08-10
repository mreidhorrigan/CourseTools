#!/usr/bin/env bash
# verify.command -- the network-free gate. Double-click or run before committing.
# Runs: (1) the test suite, (2) the determinism check this tool can actually
# make (same config -> byte-identical REQUEST; see research/00-retrofit-notes.md
# for why request, not Canvas's response, is the right unit here), (3)
# config-schema validation. Exits non-zero on any failure. Wire it into a
# pre-commit hook so a red tree cannot be committed. See checklist.md.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$HERE"
export ENGINE HOME
cd "$HERE"
PY="${PYTHON:-.venv/bin/python}"; [ -x "$PY" ] || PY="python3"
fail=0

echo "== 1. tests =="
if "$PY" -c "import pytest" >/dev/null 2>&1; then
  "$PY" -m pytest -q || fail=1
else
  echo "   pytest not installed. Run: uv sync --extra dev"
  fail=1
fi

echo "== 2. determinism (same config -> same request, twice) =="
# This tool's artifact is a live Canvas object, which gets its own id and
# timestamp from Canvas on every run, so "same config -> byte-identical
# Canvas response" cannot be a real contract here. tests/test_engine.py
# checks the part that is actually deterministic: building the same config
# into a request payload twice yields byte-identical JSON both times. This
# section just re-runs that subset for a visible pass/fail line.
if "$PY" -m pytest -q tests/test_engine.py -k determinism; then
  :
else
  fail=1
fi

echo "== 3. Python compilation =="
if "$PY" -m compileall -q src scripts tests; then
  :
else
  fail=1
fi

echo "== 4. config-schema validation =="
shopt -s nullglob
for cfg in commands/*.config.jsonc course/*.config.jsonc; do
  out="$("$PY" commands/_jsonc.py "$cfg" 2>&1)"
  if printf '%s' "$out" | grep -q '__CONFIG_ERROR__'; then
    echo "   INVALID $cfg: ${out#__CONFIG_ERROR__=}"
    fail=1
  else
    echo "   ok $cfg"
  fi
done

echo "== 5. portability audit =="
if "$PY" scripts/audit_portability.py; then
  :
else
  fail=1
fi

echo
if [ "$fail" -eq 0 ]; then echo "✓ verify passed"; else echo "✗ verify FAILED"; fi
# Hold the window only on an interactive double-click, not in a hook or CI.
[ -t 0 ] && { echo; read -rp "Press return to close… " _; }
exit "$fail"
