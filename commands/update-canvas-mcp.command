#!/usr/bin/env bash
# Update Canvas MCP to an explicit version, test it, and leave a reviewable Git diff.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"; cd "$ENGINE"
VERSION="${1:-}"; [ -n "$VERSION" ] || read -rp "Canvas MCP version (for example 1.7.0): " VERSION
case "$VERSION" in *[!0-9.]*|'') echo "Version must contain only digits and dots."; exit 1;; esac
"${PYTHON:-python3}" - "$VERSION" <<'PY'
from pathlib import Path
import sys
p=Path("mcp/requirements.in")
p.write_text("# Direct optional MCP dependency. Compile with the command documented in mcp/README.md.\n"+f"canvas-mcp=={sys.argv[1]}\n")
PY
UV_CACHE_DIR="${TMPDIR:-/tmp}/canvas-mcp-uv-cache" uv pip compile mcp/requirements.in \
  --universal --generate-hashes --custom-compile-command "commands/update-canvas-mcp.command $VERSION" \
  --output-file mcp/requirements.lock || exit 1
[ -x mcp/.venv/bin/python ] || uv venv mcp/.venv --python 3.12 || exit 1
UV_CACHE_DIR="${TMPDIR:-/tmp}/canvas-mcp-uv-cache" uv pip sync --python mcp/.venv/bin/python mcp/requirements.lock || exit 1
mcp/.venv/bin/canvas-mcp-server --help >/dev/null || { echo "Installed server failed its smoke test."; exit 1; }
echo "Updated and smoke-tested canvas-mcp $VERSION. Review the pin change:"
git diff -- mcp/requirements.in mcp/requirements.lock 2>/dev/null || true
echo "Run ./verify.command and review upstream release/security notes before committing."
echo; [ -t 0 ] && read -rp "Press return to close… " _
