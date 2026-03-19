#!/usr/bin/env bash
# build-extension.sh — Copy opencli Browser Bridge extension source into the
# chrome container build context so Docker can build it during image creation.
#
# Usage: ./scripts/build-extension.sh
#
# Run before: docker compose build chrome-1
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OPENCLI_EXT="$REPO_ROOT/../opencli/extension"
DEST="$REPO_ROOT/chrome/extension-src"

if [ ! -d "$OPENCLI_EXT" ]; then
  echo "ERROR: opencli extension not found at $OPENCLI_EXT"
  echo "  Expected sibling layout: .../opencli  and  .../opencli-admin"
  exit 1
fi

echo "Copying Browser Bridge extension source → chrome/extension-src/ ..."
rm -rf "$DEST"
mkdir -p "$DEST"
cp "$OPENCLI_EXT/manifest.json"  "$DEST/"
cp "$OPENCLI_EXT/package.json"   "$DEST/"
cp -r "$OPENCLI_EXT/src"         "$DEST/src"
cp -r "$OPENCLI_EXT/icons"       "$DEST/icons"
cp "$OPENCLI_EXT/tsconfig.json"  "$DEST/" 2>/dev/null || true
cp "$OPENCLI_EXT/vite.config.ts" "$DEST/" 2>/dev/null || true

echo "Done. Now run: docker compose build chrome-1"
