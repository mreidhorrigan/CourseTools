#!/usr/bin/env bash
# mirror.command — one-command off-machine mirror, preserving local-first ownership without
# single-disk risk. Pushes a git bundle (full history, tiny because the recipe-not-bulk hygiene
# keeps the repo small) plus the non-regenerable inputs to a destination drive or path. See
# 05-git-and-artifacts.md (P3-A) and 11-suites-and-sharing.md.
#
#   ./mirror.command [DEST]        # DEST default below; an external/cloud drive or a remote path
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
NAME="$(basename "$HERE")"
DEST="${1:-${MIRROR_DEST:-$HOME/Backups/$NAME}}"

mkdir -p "$DEST" || { echo "❌ cannot write to $DEST"; exit 1; }
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"

echo "Mirroring $NAME -> $DEST"

# 1. Full-history git bundle (small: source, configs, manifests, lockfile; no bulk).
if [ -d .git ]; then
  git bundle create "$DEST/$NAME-$STAMP.bundle" --all \
    && echo "  ✓ git bundle: $NAME-$STAMP.bundle" \
    || echo "  ⚠ git bundle failed"
else
  echo "  ⚠ not a git repo; skipping bundle"
fi

# 2. Non-regenerable inputs only (rsync the things the recipe canNOT rebuild). EDIT the list.
#    Everything in out/ models/ vendor/ is regenerable, so it is deliberately excluded.
INPUTS=( humansaves src research )   # add: source recordings, hand assets, manifests
present=()
for d in "${INPUTS[@]}"; do [ -e "$d" ] && present+=( "$d" ); done
if [ "${#present[@]}" -gt 0 ] && command -v rsync >/dev/null 2>&1; then
  rsync -a --delete "${present[@]}" "$DEST/inputs/" \
    && echo "  ✓ inputs synced: ${present[*]}" \
    || echo "  ⚠ rsync failed"
fi

# 3. OPTIONAL encryption at rest: tar + age/gpg before copying to an untrusted destination.
#    Example (uncomment, requires age):
#    tar czf - "$DEST/$NAME-$STAMP.bundle" "$DEST/inputs" | age -r "$AGE_RECIPIENT" > "$DEST/$NAME-$STAMP.tar.gz.age"

echo
echo "✓ Mirror done: $DEST"
[ -t 0 ] && { echo; read -rp "Press return to close… " _; }
