#!/usr/bin/env bash
# ============================================================================
#  DOUBLE-CLICK THIS FILE (in Finder) AFTER MOVING THE PROJECT FOLDER.
#  It rebuilds the venv from the committed lockfile and re-resolves baked-in
#  paths, then waits so you can read the result. See 06-vendoring-and-linking.md.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")" || exit 1

echo "Re-resolving this tool after a move…"

# Rebuild the pinned environment from the committed lockfile (reproducible, not re-resolved).
if command -v uv >/dev/null 2>&1; then
  uv sync || { echo "❌ uv sync failed"; }
else
  echo "⚠ uv not found. Install uv, or create the venv manually:"
  echo "    python3 -m venv .venv && .venv/bin/pip install -e ."
fi

# OPTIONAL: rebuild vendored third-party code from its setup script, if you have one.
# [ -x scripts/build_vendor.sh ] && bash scripts/build_vendor.sh

# OPTIONAL: re-download model weights, if your tool uses them.
# [ -x scripts/fetch_models.sh ] && bash scripts/fetch_models.sh

echo
echo "✓ Done. This folder is ready to use from its new location."
echo
read -n 1 -s -r -p "Press any key to close this window…"
echo
