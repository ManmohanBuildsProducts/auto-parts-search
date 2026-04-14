# Decision 015: Phase 3 closes — v3 ships as production embedding; pivot to Phase 5

**Date**: 2026-04-14
**Status**: Decided

## Context

After v3 cleared the initial +10% gate (ADR 014, promoted as production), three further iterations attempted to beat it:

- **v4 ablation (A/B/C)** — YT natural-speech pairs, Aksharantar transliteration pairs, and LLM-generated Hinglish bridge pairs. Tested independently + combined.
- **v5** — drops Hinglish bridge + raw YT chunks; keeps filtered Aksharantar; adds DeepSeek-rewritten "query-ified" YT pairs (mechanic monologue → user-query form).

All four failed their gates.

## Results (joint-pool graded nDCG@10, dev-149)

| Model | Pairs | vs v3 | Gate | Result |
|-------|-------|-------|------|--------|
| v3 (production) | 7,828 | — | — | — |
| v4a (+ YT raw) | 8,204 | **−6.8%** | +10% | ❌ |
| v4b (+ YT + Aksharantar) | 11,864 | **+2.4%** | +10% | ❌ |
| v4c (+ YT + Aks + Hinglish) | 14,478 | **−2.7%** | +10% | ❌ |
| v5 (+ queryified YT + Aks) | 11,827 | **−1.6%** | +5% | ❌ |

## Key findings

1. **Hinglish bridge (DeepSeek-generated Devanagari renderings) is NOISE.** v4c regressed vs v4b despite adding 2,614 LLM-generated transliterations. Don't ship LLM-generated transliteration as training positives.

2. **Raw YouTube chunks as training pairs hurt the model (−6.8%).** Mechanic monologue ≠ user query. The linguistic register is wrong.

3. **Aksharantar transliteration pairs carry.** v4b gained +2.4% over v3; every other variant that dropped Aksharantar regressed or stayed flat. This is the only free-data source that reliably helps at our scale.

4. **YT query-ification recovers symptom signal (+13.7% in v5)** but trades it for misspelled regression (−20.8%). Zero-sum at current data scale.

5. **BGE-m3 + MNR + 11K positives is near-converged for our task.** Four different data-augmentation strategies all landed in the −3% to +2.5% band. The data ceiling is hit.

## Decision

1. **Ship v3 as the production embedding model.** `ManmohanBuildsProducts/auto-parts-search-v3` stays in the golden METADATA scorecard.

2. **Do NOT promote v4a/b/c, v5.** All three v4 variants and v5 fail their gates. Discarded.

3. **Close Phase 3.** No further embedding-data or recipe iterations. Next issue in search quality gets solved in Phase 5 (hybrid retrieval), not here.

4. **Pivot to Phase 5.** The architecture gap v5 exposed (misspelling tolerance, part-number search) is fundamentally a BM25/fuzzy-search problem. Phase 5's hybrid stack (Meilisearch BM25 + embedding rerank + query classifier) solves it natively.

## What goes to production

- **Embedding model**: `ManmohanBuildsProducts/auto-parts-search-v3` (private HF)
- **Pair set**: `data/training/golden/all_pairs_v2.jsonl` (SHA `7157b634…`)
- **Benchmark**: `data/training/golden/benchmark_dev.json` (149 q) + `benchmark_test.json` (46 q, sealed)
- **Scorecard vs BGE-m3 base**: +35% graded nDCG@10 on joint-pool, +68% symptom, +57% hindi_hinglish, +48% brand_as_generic

## Learnings captured in memory

- `memory/learnings.md`: "Query-ification addresses symptom but costs misspelled" (added in this ADR)
- `memory/feedback_never_trade_quality_silently.md`: confirmed — every quality-risk decision in v4/v5 was flagged
- `memory/feedback_training_checkpoints.md`: confirmed working; all v4/v5 runs had best-on-dev

## When to revisit Phase 3

Only revisit embedding improvements when ANY of:

1. **Real user query logs arrive** (from T506 pilot or later customer deployment) — replaces our judge-based dev set with ground truth
2. **Phase 5 hybrid retrieval exposes a specific semantic gap** not solvable by BM25 tweaks
3. **New multilingual base model** beats BGE-m3 by ≥5% on Hindi out-of-the-box (candidates: Alibaba gte-multilingual-base v2, Jina v4, Sarvam's own embedding model if they release one)

## Links

- [ADR 006](./006-phase3-training-loop.md) — Phase 3 loop structure
- [ADR 013](./013-binary-labels-mnr-for-v1.md) — binary + MNR wins over CoSENT
- [ADR 014](./014-gate-vs-discipline-upgrades.md) — promotion gate policy
- v4 ablation artifacts: `data/training/experiments/2026-04-14-v4/`
- v5 artifacts: `data/training/experiments/2026-04-14-v5/`
- External datasets: `data/external/processed/` (YT transcripts, Aksharantar, Hinglish bridge)
