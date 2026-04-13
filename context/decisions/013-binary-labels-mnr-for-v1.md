# Decision 013: Binary labels + MNR loss for production v1 (CoSENT deferred)

**Date**: 2026-04-13
**Status**: Decided

## Context

Phase 3 plan (`context/plans/phase3-training-loop.md`) called for two decisions after the first training loop:

- **T303c** — pair schema: graded (0.0/0.4/0.5/0.85/1.0) vs binary (label==1.0 only)
- **T303d** — loss function: CoSENT (graded) vs MultipleNegativesRanking (binary)

Both decisions were meant to be **evidence-based** — run a 1-epoch experiment comparing the two, then pick.

## Experiment

We already had **v1.2** (BGE-m3 fine-tuned with MNR loss on label==1.0 positives only). For the comparison arm, we trained **v2** with CoSENT loss on all 26,760 graded pairs (same base, same epoch count, same pair source — only schema+loss differ).

Both models were benchmarked on the `benchmark_dev_graded_joint.jsonl` pool (149 dev queries × top-20 candidates unioned from v1.2 and v2 after LLM judging). Joint pool eliminates the pool-bias that favored v1.2 in the initial v2 eval.

## Result

Fair comparison (pool overlap 1.0 for both fine-tuned models):

| Model | graded nDCG@10 | graded Recall@5 | vs BGE-m3 base |
|---|---|---|---|
| BGE-m3 base | 0.403 | 0.416 | — |
| **v1.2 (MNR + binary)** | **0.544** | **0.479** | **+35% / +15%** |
| v2 (CoSENT + graded) | 0.326 | 0.263 | **−19% / −37%** |

v2 loses every single query category. Most severe regressions: misspelled (−47%), symptom (−44%), hindi_hinglish (−38%), part_number (−59%).

## Decision

1. **Schema (T303c): binary labels** (label == 1.0 only) for the next production training run.
2. **Loss (T303d): MultipleNegativesRankingLoss** with in-batch negatives.
3. **Production model: v1.2** (`ManmohanBuildsProducts/auto-parts-search-v1`). Not superseded.
4. **v2 is discarded** — not promoted, not a reference model. Available at `ManmohanBuildsProducts/auto-parts-search-v2` for forensics only.

## Why CoSENT regressed (hypotheses, not verified)

1. **Graded labels are heuristic, not judgmental.** Our 0.85 (HSN siblings), 0.50 (co-occurrence), 0.40 (HSN cousins) labels come from graph-structure rules, not human ranking judgments. CoSENT tries to rank pairs by exact label magnitude — amplifying rule noise as training signal.
2. **CoSENT has no in-batch negative regularization.** Unlike MNR, CoSENT doesn't benefit from randomly-sampled negatives within each mini-batch. With 26K pairs at batch 32, 1 epoch may be insufficient for the loss to converge.
3. **No checkpointing + best-on-dev.** v2 was trained 1 epoch with only a final save. The best checkpoint may have been mid-epoch, but we can't recover it.

## When to revisit

CoSENT on graded labels is **deferred, not killed**. Revisit when:

- We have LLM-judged graded labels on training pairs (not just heuristic ones) — e.g. extend T208b-style judging to the pair set. Estimated cost: ~$5-10 on DeepSeek.
- We've added checkpointing + best-on-dev selection to the training notebook (queued in `memory/feedback_training_checkpoints.md`).
- We've exhausted easier wins on the MNR path (v3 with better checkpointing, more epochs, joint pool for evaluation).

At that point, rerun the comparison with the same experimental protocol. If CoSENT still regresses on judge-graded labels, close the question permanently.

## Links

- [ADR 006](./006-phase3-training-loop.md) — Phase 3 training loop collapsed design
- [ADR 012](./012-phase3-compute-infra.md) — Colab Free + HF Hub compute
- [memory/learnings.md](../../memory/learnings.md) — "Training / Embeddings" section
- [memory/feedback_training_checkpoints.md](../../memory/feedback_training_checkpoints.md) — checkpointing discipline
- Experiment artifacts: `data/training/experiments/2026-04-13-graded/{v1.2,v2}-joint.json`
