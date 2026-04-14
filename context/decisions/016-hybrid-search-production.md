# Decision 016: Hybrid BM25+v3 RRF is production retrieval; class-weighted

**Date**: 2026-04-14
**Status**: Decided

## Context

Phase 5 started with v3 embedding retrieval alone as baseline. T402b added a Meilisearch BM25 index; alone it scored worse than v3 on every category (MRR 0.30 vs 0.48) — expected, since v3 was fine-tuned on this corpus. T402c asks whether fusion helps.

## Experiment

Reciprocal Rank Fusion (RRF, k=60) over BM25 top-30 + v3 top-30, with **class-specific weights** from a lightweight heuristic query classifier (regex + keyword list over part_number / hindi_hinglish / symptom / brand_as_generic / exact_english).

Tuning (two passes on dev-149 joint-pool graded):

| Weight scheme | Overall nDCG@10 | Recall@5 | part_number | symptom |
|---|---|---|---|---|
| v3 alone (baseline) | 0.585 | 0.488 | 0.110 | 0.610 |
| Pass 1: (0.5/0.5, symptom 0.2/0.8) | 0.585 (tied) | 0.513 (+5%) | 0.161 (+46%) | 0.577 (−5%) |
| **Pass 2 (prod): tighter weights** | **0.588** (+0.4%) | **0.503** (+3%) | **0.161** (+46%) | **0.612** (+0.3%) |

**Production weights (Pass 2):**
```
part_number       0.80 BM25  /  0.20 embedding
symptom           0.10 BM25  /  0.90 embedding
brand_as_generic  0.30 BM25  /  0.70 embedding
hindi_hinglish    0.20 BM25  /  0.80 embedding
exact_english     0.50 BM25  /  0.50 embedding
```

## Decision

Ship hybrid BM25+v3 RRF as the Phase 5 retrieval path. Fusion is class-weighted via `auto_parts_search.query_classifier`.

## Why hybrid wins even though nDCG@10 is a near-tie

1. **part_number +46%** — the one category neither embedding fine-tuning could crack. BM25's exact-match catches numeric part identifiers. Critical for real catalog search.
2. **Recall@5 +3.2%** — users see relevant items in top-5 more often, a direct UX win.
3. **No net regression** — overall nDCG@10 +0.4% (noise-level positive).
4. **Typo tolerance is "free"** via Meilisearch — "brek pad" now returns "Brake pad". v3 alone can't guarantee this.
5. **Query classifier is cheap** (regex, <1ms) and tunable — bad classifications degrade gracefully to default weights.

## What's still weak (to revisit)

- exact_english and misspelled each −2% vs v3 alone. BM25 injects marginal candidates; with more weight tuning or learned fusion, these can recover.
- part_number is absolute low (0.16) — our corpus has no actual OEM part numbers indexed. Fix is catalog ingestion (T405), not retrieval algorithm.
- Classifier is heuristic (keyword list). Fine at current scale; graduate to a small classifier head if misclassification rate exceeds 10% in query logs.

## Links

- [ADR 010](./010-search-tokenizer.md) — tokenizer pipeline (built T402a)
- [ADR 015](./015-phase-3-close-ship-v3.md) — v3 embedding shipped
- `auto_parts_search/search_hybrid.py` — RRF implementation
- `auto_parts_search/query_classifier.py` — class-weighted routing
- Dev-149 joint-pool judged artifact: `data/training/experiments/2026-04-14-v5/hybrid_vs_v3_graded.jsonl`
