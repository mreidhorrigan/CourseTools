#!/usr/bin/env bash
# Portable deterministic setup. macOS users normally double-click setup-after-move.command.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js is required for Testmaker's original JavaScript print renderer: https://nodejs.org/" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "npm is required and normally ships with Node.js: https://nodejs.org/" >&2; exit 1; }
uv sync --frozen --extra dev
npm ci --omit=optional --prefix vendor/testmaker-mcqer
echo "Deterministic Canvas Automation environment, Testmaker renderer, and verification tools are ready."
