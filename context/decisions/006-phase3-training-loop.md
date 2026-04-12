# Decision 006: Collapse Phase 3 (pair gen) + Phase 4 (model) into one training loop

**Date**: 2026-04-12
**Status**: Decided
**Supersedes**: Phase 3 and Phase 4 sections of prior TASKS.md

## Context
The original roadmap treated pair generation (Phase 3) and model training (Phase 4) as sequential phases. Between 2026-04-09 and 2026-04-11, Phase 3 tasks T200 (HSN hierarchy pairs), T201 (ITI system pairs), T202 (diagnostic chain pairs), and T206 (merge to `all_pairs_v2.jsonl`) were worked on open-loop — generated without ever training a model on them. All four were subsequently trashed (Cline Kanban on 2026-04-11). The root cause is structural: without a model in the loop, pair quality cannot be evaluated, so "done" is a guess.

## Decision
Treat pair generation and model training as a single loop. The atomic unit of work is the triple:

```
(pair_generation_strategy, model_checkpoint, benchmark_score)
```

No pair-generation variant is "done" until a model has been trained on it and benchmarked.

## T206 post-mortem
The trashed Phase 3 work produced `hsn_hierarchy_pairs.jsonl` (1,300 lines), `system_pairs`, `diagnostic_pairs`. The decision to discard is documented in `memory/regressions.md`. Summary: graded-similarity labels were committed to without validating against a model; the "20%+ improvement over v1" criterion was unmeasurable because v1 didn't exist yet.

## T303 split
The old `T303 L` is replaced by:
- **T303a (S, P0)** — `training/evaluate.py`: `evaluate(model_path, benchmark_path) -> {mrr, ndcg@10, recall@5, zero_result_rate_by_type}`. Baseline with `all-MiniLM-L6-v2` to prove the harness works.
- **T303b (S, P0)** — Base-model shootout: BGE-m3, Jina v3, multilingual-e5-large, OpenAI `text-embedding-3-large`, Cohere `embed-multilingual-v3`, Sarvam Indic embedding if released. Pick best. ADR 012.
- **T303c (M, P0)** — Pair schema decision: graded (0.0–1.0 from graph distance) vs binary. ADR 013.
- **T303d (M, P0)** — Loss function: MultipleNegativesRankingLoss (default), CoSENTLoss (graded), MarginMSELoss (distillation). ADR 014.
- **T303e (L, P0)** — Single training run. If <10% over best base from T303b, stop and revisit pair generation. Do not tune hyperparameters first.

## Consequences
- TASKS.md Phase 3 and Phase 4 sections are replaced by a single "Phase 3: Training loop" section.
- The detailed plan lives at `context/plans/phase3-training-loop.md`.
- Pair-generation experiments live under `data/training/experiments/<date>-<hypothesis>/` — never mutate `data/training/golden/`.
