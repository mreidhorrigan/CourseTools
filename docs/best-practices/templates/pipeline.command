#!/usr/bin/env bash
# pipeline.command — run a staged pipeline ONE STEP AT A TIME (the stepwise driver).
# A profile (one run / variant) is configured once (profiles/<name>/profile.config.jsonc + configs/),
# then each step runs in order, inheriting that profile via the commands/_lib.sh overlay. Reads the
# ordered steps from pipeline.json (via _pipeline.py). See 13-staged-pipelines-and-shared-config.md.
#
#   • DOUBLE-CLICK                              -> lists profiles + usage.
#   • ./pipeline.command <name>                 -> show ordered steps with [done]/[NEXT] + the next command.
#   • ./pipeline.command <name> <n|step|next>   -> run ONE step (gated steps confirm first).
#
# Equivalent to running one step yourself with the profile active:  PROFILE=<name> ./commands/<step>.command
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
PY="$ENGINE/.venv/bin/python"; [ -x "$PY" ] || PY="python3"
hold() { echo; [ -t 0 ] && read -rp "Press return to close… " _ || true; }

NAME="${1:-}"; SEL="${2:-}"

# No profile named -> list profiles + usage.
if [ -z "$NAME" ]; then
  echo "Profiles (profiles/<name>/):"
  ls -1 "$ENGINE/profiles" 2>/dev/null | grep -v '^_' | sed 's/^/  /' || true
  echo
  echo "Usage:"
  echo "  ./pipeline.command <name>                 # show the ordered steps + status"
  echo "  ./pipeline.command <name> <n|step|next>   # run one step (configured by that profile)"
  hold; exit 0
fi

PH="$ENGINE/profiles/$NAME"
if [ ! -d "$PH" ]; then
  echo "❌ No profile: profiles/$NAME"
  echo "   Start one:  mkdir -p profiles/$NAME/configs && cp <handbook>/templates/profile.config.jsonc profiles/$NAME/profile.config.jsonc"
  hold; exit 1
fi

# No step selected -> show the ordered pipeline with status.
if [ -z "$SEL" ]; then
  echo "Profile: $NAME    ($PH)"; echo
  "$PY" "$HERE/_pipeline.py" list "$PH" | while IFS=$'\t' read -r n step st desc; do
    case "$st" in done) mark="✓ done";; next) mark="→ NEXT";; *) mark="  todo";; esac
    printf "  %-7s %-2s %-18s %s\n" "$mark" "$n" "$step" "$desc"
  done
  nextstep="$("$PY" "$HERE/_pipeline.py" resolve "$PH" next 2>/dev/null || true)"; nextstep="${nextstep#GATED }"
  echo
  if [ -n "$nextstep" ]; then
    echo "Next:   ./pipeline.command $NAME next        # runs: $nextstep"
  else
    echo "All core steps complete."
  fi
  echo "Optional:"
  "$PY" "$HERE/_pipeline.py" optional | while IFS=$'\t' read -r step kind desc; do
    printf "    %-18s %-9s %s\n" "$step" "[$kind]" "$desc"
  done
  hold; exit 0
fi

# A step was selected -> resolve and run exactly one, with the profile active.
resolved="$("$PY" "$HERE/_pipeline.py" resolve "$PH" "$SEL" 2>/dev/null || true)"
if [ -z "$resolved" ]; then
  echo "❌ Unknown step: '$SEL'  (use a step number, a step name, or 'next')"; hold; exit 1
fi
gated=""; case "$resolved" in "GATED "*) gated=1; resolved="${resolved#GATED }";; esac
cmd="$HERE/$resolved.command"
if [ ! -e "$cmd" ]; then
  echo "❌ No launcher for step '$resolved' (expected commands/$resolved.command)"; hold; exit 1
fi
if [ -n "$gated" ]; then
  echo "⚠ Step '$resolved' is GATED (network / API / local model)."
  if [ -t 0 ]; then
    read -rp "Run it for profile '$NAME'? [y/N] " ok
    case "$ok" in y|Y|yes|YES) ;; *) echo "Skipped."; hold; exit 0;; esac
  fi
fi

echo "▶ Step '$resolved' for profile '$NAME'  (PROFILE=$NAME)…"; echo
PROFILE="$NAME" exec bash "$cmd"
