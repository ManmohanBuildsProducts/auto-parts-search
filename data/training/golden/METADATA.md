# Golden Training Set Metadata

**Current version:** *not yet promoted — placeholder.*

This directory will be populated under T603e (see `context/plans/phase2b-cleanup.md`). Until then, the files in `data/training/*.jsonl` serve as a *de-facto* reference but do not meet the promotion criteria:

- [ ] `random.seed(42)` added to all generators (T603a)
- [ ] Raw data manifest entry pointing to a committed snapshot (T603b/c)
- [ ] Deterministic regeneration verified (two identical runs)
- [ ] Benchmark test/dev split applied (T208)

## Schema (once populated)

```yaml
version: v1
promoted_at: YYYY-MM-DD
from_experiment: data/training/experiments/<dir>/
scrape_snapshot: scrape-v1-2026-04-10    # reference to data/raw/MANIFEST.md
random_seed: 42
git_commit: <hash>
pair_counts:
  vocabulary: 1593
  catalog: 17372
  total: 18965
benchmark:
  queries: 195
  dev_queries: 150
  test_queries: 45
test_scores:
  model_path: models/autoparts-v1/
  base_model: BAAI/bge-m3
  mrr: 0.xx
  ndcg_at_10: 0.xx
  recall_at_5: 0.xx
```
