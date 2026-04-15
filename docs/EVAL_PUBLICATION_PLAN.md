# Eval Publication Plan (T305)

**Goal:** Publish an HF-based credibility package so prospects' CTOs can independently verify our Hindi/Hinglish retrieval claims — beating "+38% over BGE-m3 on our private dev set" with **"v3 beats OpenAI text-embedding-3-large by X% on a public benchmark + public eval script."**

Source of this plan: 2026-04-15 discussion triggered by user's friend pushing for an external benchmark; user clarified end goal is an HF publication for credibility. Supersedes the "T305 deferred" line in ADR 015.

---

## What we already have (do NOT rebuild)

| Metric | Where it's computed | Models we have numbers for |
|---|---|---|
| MRR | `training/evaluate.py` | MiniLM, BGE-m3, v1.2, v3, v4a/b/c, v5 |
| nDCG@10 (binary) | same | same |
| Recall@5 (binary) | same | same |
| Zero-result rate @10 (overall + per-category) | same | same |
| Per-category nDCG@10 (6 types) | `training/evaluate_graded.py` | BGE-m3, v1.2, v3, v4a/b/c, v5 |
| Graded nDCG@10 (LLM-judged) | same | same |
| Graded Recall@5 | same | same |
| Pool overlap (fairness) | same | same |
| LLM-judge joint-pool infrastructure | `scripts/judge_benchmark.py` | DeepSeek V3 verified (96% agreement with Claude Opus) |
| Sealed test set (46 queries) | `benchmark_test.json` | **Not yet used** — reserve for final publication only |

## What's missing — the T305 build-out

### Eval metrics to add (~1 hr)

Extend `evaluate_graded.py`:
- **Precision@1** — MTEB standard for "did the top hit land"
- **MAP@10** — MTEB standard for ranking quality across cutoffs
- **Recall@10, Recall@20** — for small-corpus contexts
- **Latency measurement wrapper** — p50 / p95 / p99 across N queries per model
- **Cost per 1K queries** — derived from model API pricing (OpenAI $0.13/M in, Cohere $0.10/M, local $0.00)

### External models to benchmark (~3 hr + ~$3)

1. `OpenAI/text-embedding-3-large` — via API, 3072-dim
2. `Cohere/embed-multilingual-v3.0` — via API, 1024-dim
3. `jinaai/jina-embeddings-v3` — local (retry fairseq-free install, or via HF Inference API)
4. `intfloat/multilingual-e5-large` — local (already cached)
5. `BAAI/bge-m3` — baseline (already cached)
6. **v3 (ours)** — `ManmohanBuildsProducts/auto-parts-search-v3`

Methodology:
- Build joint pool = union of top-20 from all 6 models per query
- Judge once with DeepSeek V3 (~$3, ~60 min)
- Rescore all 6 against the same pool → fair comparison, every model at overlap=1.0 or near

### Deliverables (4-asset publication package)

#### Asset 1 — HF Dataset: `ManmohanBuildsProducts/auto-parts-search-benchmark`
- `benchmark_dev.json` (149 queries, 6 types)
- `benchmark_test.json` (46 sealed queries)
- `benchmark_dev_graded_joint.jsonl` — graded labels
- README: query distribution, judge methodology, provenance (KG source, catalog scrape snapshot), license
- Loader script for `datasets.load_dataset()`
- License: CC-BY 4.0

#### Asset 2 — Model card for `auto-parts-search-v3`
Add eval table to README.md:

| Model | nDCG@10 | Recall@5 | P@1 | MAP@10 | Hindi/Hinglish | Symptom | Part# | Latency p50 | $/1K |
|---|---|---|---|---|---|---|---|---|---|
| BGE-m3 | … | … | … | … | … | … | … | … | $0 |
| OpenAI v3-large | … | … | … | … | … | … | … | … | $0.X |
| Cohere mult-v3 | … | … | … | … | … | … | … | … | $0.X |
| Jina v3 | … | … | … | … | … | … | … | … | $0 |
| e5-large | … | … | … | … | … | … | … | … | $0 |
| **v3 (ours)** | **…** | **…** | **…** | **…** | **…** | **…** | **…** | **…** | **$0** |

Plus: training data provenance, recipe summary, intended use, limitations, citation.

#### Asset 3 — Reproducible eval script: `scripts/bench_external.py`
Single command:
```bash
python3 -m scripts.bench_external --output docs/eval_report_data.json
```
- Pulls all 6 models (HF + API)
- Builds joint pool
- Runs judge (cached — reuses existing labels where candidate_ids match)
- Writes JSON + markdown table
- Makes results reproducible by anyone with the API keys

#### Asset 4 — Writeup: `docs/EVAL_REPORT.md`
Sections:
1. Problem (Hindi/Hinglish auto-parts search is broken everywhere)
2. Benchmark construction (149 dev queries, 6 types, joint-pool LLM-judged)
3. Methodology (hybrid pipeline, class-weighted fusion, caveats)
4. Results table (6 models, ~12 metrics)
5. Where v3 wins, where it loses (honest)
6. Limitations (dev set only; sealed test reserved; judge is DeepSeek not human; corpus is 27K)
7. Cite: models used + datasets + source scripts

Link from LinkedIn + sales deck + cold-outreach DMs.

### Bonus — submit to MTEB leaderboard

MTEB accepts community-contributed tasks.
- Add an "Indian Auto Parts Retrieval" task under MTEB's retrieval category
- Submit via PR to `embeddings-benchmark/mteb` repo
- v3 gets listed on the public leaderboard alongside OpenAI/Cohere

Moderate effort (~4 hr), high asymmetric payoff.

---

## Proposed ~12-metric table (shipped on the model card + writeup)

MTEB-aligned (credibility bar):
1. **nDCG@10** (graded) — primary retrieval metric
2. **Recall@5**
3. **Precision@1** — "did the top hit land"
4. **MAP@10** — ranking quality across cutoffs
5. **MRR@10**

Domain-specific (our moat):
6. Per-category nDCG@10: exact_english
7. Per-category nDCG@10: misspelled
8. Per-category nDCG@10: hindi_hinglish
9. Per-category nDCG@10: symptom
10. Per-category nDCG@10: brand_as_generic
11. Per-category nDCG@10: part_number
12. Zero-result rate @10 (overall)

Operational (sales-useful):
13. Latency p50 (ms)
14. Latency p95 (ms)
15. Cost per 1K queries ($)

15 metrics. Every one decision-useful. Every one either MTEB-aligned or shows a specific fact a prospect cares about.

This is the counter to "25-30 metrics": **more metrics obscure the story**. A prospect's CTO reading the model card should see the win in <30 seconds of scanning; 30 metrics makes that impossible.

---

## Effort estimate

| Step | Hours | Cost |
|---|---|---|
| Extend `evaluate_graded.py` with P@1 + MAP@10 + Recall@10/20 | 30 min | $0 |
| Build `scripts/bench_external.py` (all-vs-all joint pool, 6 models) | 3 hr | ~$3 (OpenAI + Cohere) |
| Latency + cost measurement module | 1 hr | $0 |
| HF Dataset repo upload | 30 min | $0 |
| Model card update | 1 hr | $0 |
| `docs/EVAL_REPORT.md` writeup | 2 hr | $0 |
| **Core publication package subtotal** | **~8 hr** | **~$3** |
| MTEB task submission (bonus) | 4 hr | $0 |
| **Total if MTEB is included** | **~12 hr** | **~$3** |

---

## Execution order (next session)

1. Set up OpenAI + Cohere API keys (user action)
2. Extend `training/evaluate_graded.py` with Precision@1, MAP@10, Recall@10/20
3. Build `scripts/bench_external.py` — runs 6 models, generates joint pool, judges, rescores
4. Run the bench ($3, ~60 min judge time)
5. Build latency + cost wrapper
6. Write `docs/EVAL_REPORT.md`
7. Update `ManmohanBuildsProducts/auto-parts-search-v3` model card on HF
8. Create and upload `ManmohanBuildsProducts/auto-parts-search-benchmark` HF Dataset
9. (Bonus) Submit MTEB task

---

## Why this matters for the LinkedIn post

Swap "+38% over BGE-m3 on our private dev set" for:
> "v3 beats OpenAI text-embedding-3-large by X% on Hindi queries on a publicly reproducible benchmark published at `huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-benchmark`"

The first is a claim. The second is a claim with independent-verifiability baked in. For a solo founder pitching to Indian e-comm CTOs, the second is ~10× more convincing.

## References (for the next agent)

- ADR 015: `context/decisions/015-phase-3-close-ship-v3.md` — where T305 was originally deferred
- ADR 016: `context/decisions/016-hybrid-search-production.md` — hybrid pipeline
- Scoring utilities: `training/evaluate_graded.py`
- Judge: `scripts/judge_benchmark.py`
- Existing graded labels: `data/training/experiments/2026-04-14-v5/hybrid_vs_v3_graded.jsonl` (reusable for cached judgments when candidate_ids match)
- MTEB: `https://github.com/embeddings-benchmark/mteb`
