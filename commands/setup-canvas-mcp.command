#!/usr/bin/env bash
# Saves Canvas MCP credentials in macOS Keychain; never writes the token to disk.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE="$(cd "$HERE/.." && pwd)"
cd "$ENGINE"
command -v uv >/dev/null 2>&1 || { echo "uv is required: https://docs.astral.sh/uv/"; exit 1; }
[ -x mcp/.venv/bin/python ] || uv venv mcp/.venv --python 3.12 || exit 1
uv pip sync --python mcp/.venv/bin/python mcp/requirements.lock || exit 1
echo "Canvas MCP credential setup"
read -rp "Canvas API URL (include /api/v1): " CANVAS_API_URL
case "$CANVAS_API_URL" in https://*/api/v1) ;; *) echo "Expected an HTTPS URL ending in /api/v1."; exit 1;; esac
read -rsp "Canvas API token: " CANVAS_API_TOKEN; echo
[ -n "$CANVAS_API_TOKEN" ] || { echo "Token cannot be empty."; exit 1; }
security add-generic-password -U -a "$USER" -s canvas-automation-mcp-url -w "$CANVAS_API_URL" >/dev/null
security add-generic-password -U -a "$USER" -s canvas-automation-mcp-token -w "$CANVAS_API_TOKEN" >/dev/null
unset CANVAS_API_TOKEN
echo "Saved to macOS Keychain. Restart Codex (or open a new session) to load the Canvas MCP server."
read -rp "Press return to close… " _
