#!/usr/bin/env bash
# Builds a sanitized collaborator ZIP. Settings: build-distribution.config.jsonc.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ENGINE="$(cd "$HERE/.." && pwd)"
export ENGINE HOME; cd "$ENGINE"; source "$HERE/_lib.sh"
CONFIG="$HERE/build-distribution.config.jsonc"; eval "$(read_config "$CONFIG")"
launch "$release_dir" -- "$ENGINE/.venv/bin/python" scripts/build_distribution.py --root "$ENGINE" --config "$CONFIG"
if [ -t 0 ]; then echo; read -rp "Press return to close… " _; fi
