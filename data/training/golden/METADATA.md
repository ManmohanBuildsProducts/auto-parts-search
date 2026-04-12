# Golden Training Set Metadata

**Current version:** golden-v1
**Promoted at:** 2026-04-12
**Promoted from:** `data/training/*.jsonl` (top-level) after T603-verify passed

## Provenance

| Criterion | Status |
|-----------|--------|
| `random.seed(RANDOM_SEED)` in all generators (T603a) | ✅ Module-level + per-function `rng = Random(42)` in `training/catalog_pairs.py`; per-function in `training/vocabulary_pairs.py`; `training/benchmark.py` uses no random |
| Deterministic regeneration verified (T603-verify) | ✅ Two consecutive `python3 -m auto_parts_search pairs` runs produced byte-identical output (2026-04-12) |
| Raw data snapshot manifest (T603b) | 🟡 Template present at `data/raw/MANIFEST.md` with TBD SHA256 for scrape-v1-2026-04-10; B2 upload pending (T603c) |
| Benchmark dev/test split (T208) | ❌ Not yet done — benchmark.json is the full 195-query set; split lives in Phase 3 plan |

## SHA256 hashes (as promoted)

| File | SHA256 | Rows |
|------|--------|------|
| `all_pairs.jsonl` | `f3407c0c94bb9ba520a7b1cba476e4f1871c3ac38c6ce8aca87955ba1dc5ea1a` | 18,947 |
| `catalog_pairs.jsonl` | `4a84adf2f4a571f12a14784ae02bf3efa11c0b05763a400f9164f8c9ce82b5aa` | 17,354 |
| `vocabulary_pairs.jsonl` | `b20ef9faa706d7a042cf38255336530f46ea3a30f061ec3de682d18428116e62` | 1,593 |
| `benchmark.json` | `585bfdd5004757ffa8682b3bafaf4dd3856c9f15d83eab772ddfdaadfe843fbb` | 195 queries |

## Upstream dependencies

- Scrape snapshot: **TBD** — will be `scrape-v1-2026-04-10` once uploaded to Backblaze B2 per T603c.
- Catalog-pair seed: `RANDOM_SEED = 42` from `auto_parts_search/config.py`.
- Generator commits: latest as of this promotion is `7890da2` (master).

## When to bump to v2

Bump when ANY of:
1. New pair source added (e.g. `hsn_hierarchy_pairs`, `iti_system_pairs`, `iti_diagnostic_pairs` — all queued under Phase 3 Track A).
2. Pair schema changes (binary → graded labels — ADR 013, when written).
3. Scrape re-run that materially changes the input catalog.

Experiments branch into `data/training/experiments/<YYYY-MM-DD>-<hypothesis>/` and do NOT modify this directory. Promotion is a deliberate commit that updates the hashes above + the model benchmark table below.

## Models trained on this set

_None yet._ First model run is T302 (Phase 3 training loop). When a model ships, append:

```
| Model | Base | Test nDCG@10 | Test Recall@5 | Commit | Notes |
|-------|------|--------------|---------------|--------|-------|
```
