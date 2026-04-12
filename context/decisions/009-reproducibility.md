# Decision 009: Reproducibility — manifest + seed + golden run

**Date**: 2026-04-12
**Status**: Decided

## Context
Today the pipeline is not reproducible:
- `data/raw/` is gitignored (~hundreds of MB). A fresh clone cannot regenerate training data without re-scraping live sites, which have drifted.
- `training/catalog_pairs.py` uses `random.choice` for negatives without `random.seed()` — same input produces different pair files on rerun.
- There is no distinction between "the pair file we actually trained on" vs "the pair file a current experiment produced."

Consequence: we cannot verify our own "Phase 1 = 18,965 pairs" claim months from now. A prospect asking "show me the training data for the model you're selling" cannot be answered.

## Decision
Three independent fixes, all P0.

### (a) Snapshot `data/raw/` with a manifest
- Upload `data/raw/` tarballs to Backblaze B2 (or S3/R2). Cost: <$1/mo for <20GB.
- Commit `data/raw/MANIFEST.md` listing each snapshot: SHA256, URL, row count per file, scrape date.
- Script `scripts/fetch_raw.py` reads the manifest and downloads the latest snapshot.

### (b) Deterministic pair generation
- Add `random.seed(42)` at the top of every module in `training/` that uses `random`.
- Document the seed in `data/training/golden/METADATA.md`.
- Rationale: without this, "v1 vs v2 model" comparisons conflate model differences with nondeterministic data differences.

### (c) Golden run convention
Directory layout:
```
data/training/golden/           # blessed reference, never mutated
  all_pairs.jsonl
  benchmark.json
  vocabulary_pairs.jsonl
  catalog_pairs.jsonl
  METADATA.md                   # scrape version, seed, commit hash, date

data/training/experiments/
  2026-04-18-hard-negatives/    # branched from golden
    all_pairs.jsonl
    model_checkpoint.pt
    benchmark_results.json
    NOTES.md                    # hypothesis, diff from golden, results
```
Experiments branch from golden. Experiments that beat golden get promoted via a deliberate commit that updates `METADATA.md` and `MANIFEST.md`. Never overwrite golden silently.

## Migration
- Current files in `data/training/*.jsonl` + `benchmark.json` become golden-v1 on promotion. Move them via the T600-series cleanup task once the metadata is written.

## Consequences
- Adds one manifest file, one README, three `random.seed(42)` lines — minimal code.
- Enables "bit-identical rerun by a cold clone" as a property we can claim.
