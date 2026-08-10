#!/usr/bin/env bash
# Portable deterministic setup. macOS users normally double-click setup-after-move.command.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
uv sync --frozen --extra dev
echo "Deterministic Canvas Automation environment and verification tools are ready."
