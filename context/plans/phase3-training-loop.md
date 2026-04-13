# Phase 3 Plan: Training loop (replaces old Phase 3 + Phase 4)

**Status**: Not started
**Depends on**: Phase 2b cleanup (SQLite KG + ITI re-extraction + reproducibility harness)
**Blocks**: Phase 5 (search API)
**Decision**: `context/decisions/006-phase3-training-loop.md`

## Objective
Produce a fine-tuned embedding model that beats the best publicly-available multilingual base model on our 195-query benchmark by ≥10%, measured on a held-out test split. Achieve this via closed-loop iteration on `(pair_generation_strategy, model_checkpoint, benchmark_score)` triples rather than open-loop pair generation.

## The loop

```
  ┌─────────────────────────────────────────────────────┐
  │  Generate pairs (experiment branch, seeded, graded) │
  └────────────────────────────┬────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────┐
  │  Fine-tune base model (frozen seed, logged config)  │
  └────────────────────────────┬────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────┐
  │  Evaluate (harness: mrr, ndcg@10, recall@5 by type) │
  └────────────────────────────┬────────────────────────┘
                               │
                               ▼
  ┌─────────────────────────────────────────────────────┐
  │  If better than golden → promote. Else → iterate.   │
  └─────────────────────────────────────────────────────┘
```

## Tasks (dependency order)

| ID | Task | Size | Priority | Depends on | DoD |
|----|------|------|----------|------------|-----|
| T303a | Build `training/evaluate.py` | S | P0 | benchmark.json exists | Function signature: `evaluate(model_path, benchmark_path) -> {mrr, ndcg@10, recall@5, zero_result_rate_by_type}`. Baseline with `all-MiniLM-L6-v2`. |
| T208 | Split benchmark into dev/test (deterministic seed) | S | P0 | — | `benchmark_dev.json` (~150q) + `benchmark_test.json` (~45q). Test set sealed — only touched for final model release. |
| T208b | Expand benchmark ground-truth per query to top-20 graded {rel, marginal, irr} | M | P0 | T208 | Labels via LLM judge (GPT-4 or Claude) with manual spot-check on 20 queries. Enables nDCG. |
| T300/T303b | Base-model shootout | S | P0 | T303a | Benchmark: BGE-m3, Jina v3, multilingual-e5-large, OpenAI `text-embedding-3-large`, Cohere `embed-multilingual-v3`, Sarvam Indic embed (if released). Committed: `context/decisions/012-base-model.md`. |
| T303c | Pair schema decision (graded vs binary) | M | P0 | T303b | ADR 013 with evidence from a 1-epoch training run comparing label types on the chosen base. |
| T303d | Loss function decision | M | P0 | T303c | ADR 014: MultipleNegativesRanking (default), CoSENT (graded), MarginMSE (distill). Chosen based on T303c findings. |
| T200b | Generate HSN-hierarchy graded pairs | M | P0 | SQLite KG (Phase 2b) | `data/training/experiments/<date>-hsn-hier/hsn_hierarchy_pairs.jsonl`. Graded labels from graph distance (sibling=0.85, cousin=0.4). |
| T201b | Generate ITI system-membership pairs | M | P0 | SQLite KG + ITI v2 | Pairs from `in_system` edges. `system_pairs.jsonl` in experiment dir. |
| T202b | Generate ITI diagnostic chain pairs | M | P0 | ITI v2 | Pairs from `caused_by` edges. `diagnostic_pairs.jsonl`. |
| T205b | Generate ASDC task-parts pairs | S | P1 | asdc_tasks.json | `task_pairs.jsonl`. |
| T203 | Generate NHTSA compat pairs (4W Indian-overlap models only) | M | P1 | nhtsa_recalls.json | `compat_pairs.jsonl`. |
| T206b | Merge golden pair set | S | P0 | T200b,T201b,T202b | `data/training/golden/all_pairs_v2.jsonl` + METADATA update. Promoted only after beating golden-v1 model. |
| T302 | Train v1 (vocab+catalog only, chosen base, chosen loss) | M | P0 | T303d | First checkpoint. Must beat best base by ≥10% on dev to proceed. |
| T303e | Train v2 (v1 pairs + KG pairs) | L | P0 | T302,T206b | If ≥10% over v1 on dev, promote; else iterate. |
| T305 | External benchmark: OpenAI `text-embedding-3-large` + Cohere `embed-multilingual-v3` on our test set | S | P0 | T303e | Side-by-side table in `context/decisions/015-v2-model-results.md`. |
| T307 | ONNX quantization | M | P1 | T303e | p50/p95 latency report. |

## Budget guardrails
- If T303e < 10% over best base, stop. Do not tune hyperparameters. Revisit pair generation or base choice.
- If T303e < OpenAI/Cohere on Hindi-query subset of test set, stop. Ship BGE-m3 + rerank as v0 to customer and revisit.

## Directory discipline
- `data/training/golden/` — reference set. Changes only via deliberate promotion commits.
- `data/training/experiments/<YYYY-MM-DD>-<hypothesis>/` — all in-flight work.
- `models/` — checkpoints, gitignored. Each checkpoint has a sibling `METADATA.json` with training config + golden hash + benchmark results.

## Out of scope for Phase 3
- Hybrid search (keyword + dense fusion) — Phase 5.
- Reranker (Cohere Rerank, ColBERT) — Phase 5.
- Query classifier — Phase 5.

## Where Phase 3 runs (compute infra — see ADR 012)

Four-room architecture, $0 budget for v1:

| Step | Where it runs | Service | Cost |
|------|---------------|---------|------|
| Generate pairs from `graph.db` | Local | Laptop (Mac) | $0 |
| Fine-tune embedding model | Cloud GPU | **Google Colab Free** (T4) | $0 |
| Store trained model | Cloud | **Hugging Face Hub** private repo `ManmohanBuildsProducts/auto-parts-search-v<N>` | $0 |
| Evaluate against 195-query benchmark | Local | Laptop (Mac) — pulls model from HF | $0 |

**Per-run user workflow:** open the Colab notebook → paste HF token → Run all → walk away ~30–60 min → scorecard printed + model auto-pushed to HF.

**Fallback ladder** (only if needed):
- Colab Free hits 12-hr cap → Colab Pro ($10/mo)
- Need A100 for a specific experiment → Modal or RunPod ($1–2/hr pay-per-second)
- Want hosted demo URL after v1 → HF Spaces ($0–9/mo)

The training script + evaluation script + Colab notebook are committable to this repo. The trained model artifacts and experiments live outside (HF + gitignored `data/training/experiments/`). See ADR 012 for full rationale.
