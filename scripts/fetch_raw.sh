#!/usr/bin/env bash
# Fetch the raw-data snapshot from Hugging Face Datasets.
#
# Usage:
#   bash scripts/fetch_raw.sh                        # latest reference snapshot
#   bash scripts/fetch_raw.sh scrape-v3-2026-04-13   # specific snapshot
#
# Extracts into data/raw/ and verifies SHA256 against MANIFEST.md.

set -euo pipefail

cd "$(dirname "$0")/.."
MANIFEST="data/raw/MANIFEST.md"

if [ ! -f "$MANIFEST" ]; then
    echo "ERROR: $MANIFEST not found. Cannot determine which snapshot to fetch."
    exit 1
fi

# Pick target snapshot
if [ "${1:-}" ]; then
    TARGET="$1"
else
    # Find the first snapshot marked 'reference' in the manifest
    TARGET=$(awk '
        /^### scrape-/ { current = $2 }
        /Status:.*reference/ && current != "" { print current; exit }
    ' "$MANIFEST")
fi

if [ -z "$TARGET" ]; then
    echo "ERROR: no reference snapshot found in $MANIFEST"
    exit 1
fi

# Extract URL + SHA for that snapshot
URL=$(awk -v t="$TARGET" '
    $0 ~ "^### "t { f=1; next }
    f && /Tarball URL:/ { print $NF; exit }
' "$MANIFEST")
SHA=$(awk -v t="$TARGET" '
    $0 ~ "^### "t { f=1; next }
    f && /Tarball SHA256:/ {
        for(i=1;i<=NF;i++) if($i ~ /^`[a-f0-9]{64}`?$/) { gsub(/`/,"",$i); print $i; exit }
    }
' "$MANIFEST")

if [ -z "$URL" ] || [ -z "$SHA" ]; then
    echo "ERROR: could not parse URL or SHA for $TARGET from $MANIFEST"
    exit 1
fi

echo "=== Fetching $TARGET ==="
echo "URL: $URL"
echo "Expected SHA: $SHA"

mkdir -p data/raw
TARBALL="data/raw/${TARGET}.tar.gz"

if [ -f "$TARBALL" ]; then
    EXISTING_SHA=$(shasum -a 256 "$TARBALL" | awk '{print $1}')
    if [ "$EXISTING_SHA" = "$SHA" ]; then
        echo "Already cached: $TARBALL (SHA matches)"
    else
        echo "Cached file SHA mismatch, re-downloading..."
        rm -f "$TARBALL"
    fi
fi

if [ ! -f "$TARBALL" ]; then
    curl -sSL -o "$TARBALL" "$URL"
    ACTUAL_SHA=$(shasum -a 256 "$TARBALL" | awk '{print $1}')
    if [ "$ACTUAL_SHA" != "$SHA" ]; then
        echo "ERROR: SHA mismatch after download"
        echo "  expected: $SHA"
        echo "  actual:   $ACTUAL_SHA"
        exit 1
    fi
    echo "Downloaded + SHA verified."
fi

echo "=== Extracting into data/raw/ ==="
tar xzf "$TARBALL" -C data/raw/
echo "Done. Contents:"
ls -lh data/raw/*.jsonl
