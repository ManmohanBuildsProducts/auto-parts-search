# Golden training set

This directory holds the **blessed reference** training pairs + benchmark used to produce the current shipped model.

**Rules:**
1. Files here are never mutated by experiments.
2. Promotion is a deliberate commit that updates `METADATA.md` and the model release notes.
3. All experiments live in `data/training/experiments/<YYYY-MM-DD>-<hypothesis>/` and branch from golden.

See ADR 009 for the reproducibility convention.

## Promotion procedure

When an experiment beats the current golden on the held-out test set by ≥5% (nDCG@10 or recall@5):

1. Move the experiment's pair files into this directory (overwriting golden).
2. Update `METADATA.md`:
   - `promoted_at`: ISO date
   - `from_experiment`: path of the experiment dir
   - `scrape_snapshot`: matching entry in `data/raw/MANIFEST.md`
   - `random_seed`: the seed used (must be 42 unless justified)
   - `benchmark_results`: test-set scores that justified promotion
   - `git_commit`: hash at promotion time
3. Tag the commit: `git tag golden-v<N>`.

## Migration note (2026-04-12)

The current `data/training/*.jsonl` and `benchmark.json` files have NOT yet been moved here. They will be moved under T603e once `random.seed(42)` is added and results are regenerated deterministically. See `context/plans/phase2b-cleanup.md`.
