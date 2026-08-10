#!/usr/bin/env bash
# ============================================================================
#  DOUBLE-CLICK THIS FILE (in Finder) AFTER MOVING THIS PROJECT FOLDER, AND
#  ALSO THE FIRST TIME YOU SET IT UP. It builds the pinned environment from
#  the committed lockfile and re-resolves baked-in paths, then waits so you
#  can read the result. See 06-vendoring-and-linking.md.
# ============================================================================
set -uo pipefail
cd "$(dirname "$0")" || exit 1

echo "Setting up the deterministic Canvas tools..."

if command -v uv >/dev/null 2>&1; then
  bash scripts/setup.sh || { echo "❌ Setup failed. See the message above."; }
else
  echo "⚠ uv not found. Install it from https://docs.astral.sh/uv/, or create the venv manually:"
  echo "    python3 -m venv .venv && .venv/bin/pip install -e ."
fi

echo
if [ -x ".venv/bin/canvas-automation" ]; then
  echo "✓ Done. API commands and IMSCC generation are ready."
  echo "  Optional AI/MCP setup: commands/setup-canvas-mcp.command"
else
  echo "⚠ Setup did not finish cleanly. .venv/bin/canvas-automation was not created."
fi
echo
read -n 1 -s -r -p "Press any key to close this window…"
echo
