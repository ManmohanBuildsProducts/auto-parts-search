#!/usr/bin/env bash
# Snapshot data/raw/ to Hugging Face as a versioned dataset.
#
# Prerequisites (one-time):
#   - HF account + access token + huggingface-cli login (see scripts/HF_SETUP.md)
#   - Set HF_USERNAME env var OR edit DATASET_REPO below after first run.
#
# Per-snapshot workflow:
#   bash scripts/snapshot_to_hf.sh
#
# Output:
#   - data/raw/scrape-v<N>-<YYYY-MM-DD>.tar.gz (local; gitignored)
#   - Uploaded to HF dataset repo
#   - New entry appended to data/raw/MANIFEST.md

set -euo pipefail

HF_USERNAME="${HF_USERNAME:-ManmohanBuildsProducts}"
DATASET_NAME="auto-parts-search-raw"
DATASET_REPO="${HF_USERNAME}/${DATASET_NAME}"

if [ "$HF_USERNAME" = "TBD" ]; then
    echo "ERROR: HF_USERNAME not set. After running 'huggingface-cli login', run:"
    echo "  export HF_USERNAME=your-hf-username"
    echo "or edit this script to hardcode it."
    echo ""
    echo "See scripts/HF_SETUP.md for full setup."
    exit 1
fi

# Ensure huggingface-cli is available
if ! command -v huggingface-cli >/dev/null 2>&1; then
    echo "ERROR: huggingface-cli not found. Install with:"
    echo "  pip3 install --user huggingface_hub"
    exit 1
fi

cd "$(dirname "$0")/.."
DATE=$(date +%F)

# Figure out next version number by inspecting MANIFEST.md
NEXT_V=$(grep -oE 'scrape-v[0-9]+' data/raw/MANIFEST.md 2>/dev/null | \
    sed 's/scrape-v//' | sort -n | tail -1 | awk '{print $1+1}')
NEXT_V=${NEXT_V:-1}

TARBALL="data/raw/scrape-v${NEXT_V}-${DATE}.tar.gz"

echo "=== Creating snapshot: $TARBALL ==="
cd data/raw
shasum -a 256 *.jsonl 2>/dev/null > SHA256SUMS.txt || {
    echo "ERROR: no *.jsonl files in data/raw/. Run scrape first."
    exit 1
}
tar czf "../../${TARBALL}" *.jsonl SHA256SUMS.txt
cd ../..

TARBALL_SHA=$(shasum -a 256 "$TARBALL" | awk '{print $1}')
TARBALL_SIZE=$(du -sh "$TARBALL" | awk '{print $1}')

echo "=== Tarball: $TARBALL ($TARBALL_SIZE, SHA256: $TARBALL_SHA) ==="

echo "=== Ensuring dataset repo exists: $DATASET_REPO ==="
huggingface-cli repo create "$DATASET_NAME" --type dataset -y --organization "$HF_USERNAME" 2>/dev/null || \
    echo "(repo already exists or org flag rejected — continuing)"

echo "=== Uploading to $DATASET_REPO ==="
huggingface-cli upload "$DATASET_REPO" "$TARBALL" "$(basename "$TARBALL")" --repo-type dataset --private

HF_URL="https://huggingface.co/datasets/${DATASET_REPO}/resolve/main/$(basename "$TARBALL")"

echo ""
echo "=== Success ==="
echo "Tarball: $TARBALL"
echo "HF URL:  $HF_URL"
echo "SHA256:  $TARBALL_SHA"
echo ""
echo "Next steps:"
echo "  1. Append this snapshot entry to data/raw/MANIFEST.md"
echo "  2. Commit MANIFEST.md"
