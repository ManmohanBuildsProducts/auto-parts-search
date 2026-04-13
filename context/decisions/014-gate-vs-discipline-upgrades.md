# Decision 014: Gates apply to schema changes, not recipe discipline upgrades

**Date**: 2026-04-13
**Status**: Decided

## Context

The Phase 3 plan (`context/plans/phase3-training-loop.md`) imposed a +10% dev-MRR gate before promoting a new model to production. This was written to prevent spurious promotion from hyperparameter noise (the classic "I tuned lr and got +2%, ship it!" failure mode).

v3 was trained with disciplined upgrades over v1.2:
- Batch size 16 → 32 (more in-batch negatives for MNR)
- 1 epoch → 2 epochs with checkpointing + best-on-dev selection
- No intermediate eval → evaluate every 200 steps

Fair joint-pool comparison:

| Metric | v1.2 | v3 | Δ |
|---|---|---|---|
| graded nDCG@10 | 0.535 | 0.559 | +4.4% |
| graded Recall@5 | 0.473 | 0.486 | +2.7% |

Per-type: 4/6 categories improved (hindi +7%, misspelled +7%, part_number +41% relative though tiny absolute, brand_as_generic +3%), 2/6 tied, 0 regressions.

A strict reading of the gate says "v3 fails, keep v1.2." But the gate was written for noise-risky changes (schema, loss function, base model), not for recipe discipline.

## Decision

The +10% gate applies to **high-risk changes**:
- Pair schema (binary vs graded)
- Loss function (MNR vs CoSENT vs MarginMSE)
- Base model (BGE-m3 vs Jina vs e5)
- Pair source additions / removals (new KG source, new scrape)

Any of these can go badly — noise in the label set, incompatible loss dynamics, a base model that's secretly worse for the domain. The gate exists to prevent shipping regressions from plausible-sounding changes that didn't actually help.

The gate does **not** apply to **low-risk discipline upgrades**:
- Checkpointing + best-on-dev (strictly adds information)
- Larger batch size within hardware limits (strictly more in-batch negatives for MNR)
- More epochs *when combined with best-on-dev selection* (worst case = pick early checkpoint, never worse than fewer epochs)
- Gradient accumulation to match effective batch
- GPU utilization fixes (fp16, gradient checkpointing, dtype choices)

For discipline upgrades, the promotion rule is:
1. No regression on any category, AND
2. Net improvement on the primary metric (graded nDCG@10), AND
3. Fair comparison (joint-pool where applicable).

v3 satisfies all three. Promote.

## v3 promotion

- HF repo: `ManmohanBuildsProducts/auto-parts-search-v3` (private)
- Replaces v1.2 as production. v1.2 is retained on HF for provenance.
- Golden v2 pair set unchanged (v3 trained on the same 7,828 positives).
- METADATA updated in `data/training/golden/METADATA.md`.

## Why not weaker: "always promote the best model"?

A "whatever beats prod by any margin promotes" rule invites noise-chasing:
- Run 10 trainings with random seeds, promote the lucky one → false-positive on regression risk.
- Low-confidence hyperparameter tweaks accumulate → model drift without coherent narrative.

The discipline-upgrade exception is strict in practice: each category must hold or improve. That's hard to fake with noise.

## Why not stricter: "keep the +10% gate universally"?

A strictly-enforced universal +10% gate freezes the model between discontinuous breakthroughs. Real-world production systems improve continuously through many small disciplined upgrades. Refusing 4% gains because they're "not big enough" ships worse software.

## Links

- [ADR 006](./006-phase3-training-loop.md) — Phase 3 loop structure
- [ADR 013](./013-binary-labels-mnr-for-v1.md) — binary + MNR recipe
- [memory/feedback_never_trade_quality_silently.md](../../memory/feedback_never_trade_quality_silently.md) — user rule enforced in v3 design
- v3 artifacts: `data/training/experiments/2026-04-13-v3/`
