# Decision 017: Reopen Phase 3 as Phase 3b — catalog-aware pairs + new base model

**Date:** 2026-04-15
**Status:** Decided
**Supersedes:** Does NOT replace ADR 015 ("Phase 3 closes — v3 ships"). v3 remains the production embedding. This ADR extends ADR 015 under its own explicit reopen criterion.

## Context

ADR 015 closed Phase 3 on 2026-04-14 after four data-augmentation experiments (v4a/b/c, v5) all landed in the [−6.8%, +2.4%] band vs v3. It defined three reopen criteria; specifically:

> **(2)** Phase 5 hybrid retrieval exposes a specific semantic gap not solvable by BM25 tweaks.

Round-2 benchmarking on the production 26K corpus (completed 2026-04-15) now satisfies criterion (2).

### Round-2 findings

| Slice | v3 + BM25-tuned hybrid | OpenAI `text-embedding-3-large` | Gap |
|---|---|---|---|
| **Overall nDCG@10** | **0.430** | **0.468** | **−0.038** |
| Hindi / Hinglish | (−10 pts vs OpenAI) | — | **−0.10** |
| brand_as_generic | (−15 pts vs OpenAI) | — | **−0.15** |
| part_number | (−9 pts vs OpenAI) | — | **−0.09** |

All three losing slices are **catalog-structure-aware** queries — queries where the model has to parse actual product-name text (SparesHub OEM product names, branded 2W eauto products) and resolve to a canonical form (generic part name, part-number alias, Hindi term). BM25 tuning in round 2 already exhausted the pure-lexical lever; further gains are unavailable from BM25-side work. This is precisely the condition that ADR 015 reopen-criterion (2) encodes.

## Triggering criterion from ADR 015

**Criterion 2:** Phase 5 hybrid retrieval exposes a specific semantic gap not solvable by BM25 tweaks. — **MET.**

Criteria 1 (user query logs) and 3 (external base model +5pt Hindi out-of-the-box) are not yet met; 3 is close — see base-model survey referenced below.

## Decision

Reopen Phase 3 as **Phase 3b** with two coordinated axes of change, not one:

1. **Axis A — catalog-aware training pairs (γ set).** Mine ~7K new pairs from the production Meilisearch `parts` index using four strategies: part-number aliasing (SparesHub), brand-as-generic catalog-anchored (eauto + research seed), vehicle-compatible (eauto + bikespares), and small Hindi-catalog bridge. Add hard negatives from same-vehicle-different-system pairs. Full spec: [`context/plans/gamma-pair-mining-spec.md`](../plans/gamma-pair-mining-spec.md).

2. **Axis B — new base-model candidate.** Fine-tune on the top candidate from the 2026-04-15 base-model survey (primary: `google/embeddinggemma-300m`; runner-up: `Alibaba-NLP/gte-multilingual-base`). Full survey: [`context/research/2026-04-15-base-model-survey.md`](../research/2026-04-15-base-model-survey.md).

γ-pairs + new base are trained together. We do not attempt an "only-γ-on-BGE-m3" variant as the primary path, because ADR 015 established that pair-only changes on BGE-m3 have a +2.4% data ceiling.

## Gate

A Phase 3b candidate (call it v4-gamma) is **promoted** only if it beats:

- **v3 + BM25-tuned-hybrid baseline of 0.430 nDCG@10 on round-2 dev** by **+5% overall (≥ 0.452)**
  **OR**
- **+10% on the brand_as_generic slice** (catalog-gap is the headline problem — a candidate that closes brand_as_generic without moving overall is still a ship).

Both measured on the **round-2 dev split** (not test — test stays sealed per §"Sealed-test policy" below).

If v4-gamma passes the gate, it replaces v3 in production and a new `golden-v3` training set is promoted. If it doesn't, see "Honest caveat" below.

## Honest caveat (loud)

ADR 015 documented that v4 best was +2.4% on dev and failed the (then) +10% gate. Four augmentation experiments all converged to [−6.8%, +2.4%]. The natural prior for a similar-shape intervention (new pairs + new base) is **not** +20% — it's closer to the +3–8% range, with meaningful probability of landing in [−3%, +3%].

### Rules for a honest-numbers finish

1. **Budget:** two training runs, ≤ 1 week of wall-clock, ≤ Colab T4 + occasional Pro.
2. **Decision at gate:**
   - **≥ +5% overall OR ≥ +10% brand_as_generic** → ship v4-gamma as the new production embedding. Update `METADATA.md`. Promote γ pairs to `golden-v3`.
   - **+3% to +5% overall** → hold. Consider γ' (pair expansion) before a second base-model fine-tune. Only one γ' cycle allowed; if it doesn't close the gate, treat as the "<3%" case.
   - **<+3% overall AND <+10% brand_as_generic** → **DO NOT SHIP v4-gamma**. Publish the honest numbers (including the gap to OpenAI) in a public note, keep v3 in production, and escalate to "real user query logs" (ADR 015 criterion 1) as the next lever. No silent-rollback, no cherry-picked slices.
3. **No slice-farming.** If a run wins on some micro-slice but loses on others, it does NOT get re-labelled as "best on X". The gate is the gate.

## Sealed-test-only-at-publication policy

- Round-2 dev split is used freely for model selection and iteration.
- The round-2 test split — and the original golden-v2 `benchmark_test.json` (46 queries) — remain **SEALED**. No looking, no eval, no peeking, during training/tuning.
- **One sealed-test evaluation**, and only one, at publication time — whether the outcome is "ship v4-gamma" or "publish honest numbers, keep v3." The sealed number is the headline number in any external communication (HF card, blog post, prospect emails).
- If we somehow need more than one sealed-test run (e.g. methodology bug), we rebuild a fresh test split from raw catalog — we do not re-run the existing sealed test.

## What this changes / doesn't change

**Unchanged:**
- v3 stays in production (`ManmohanBuildsProducts/auto-parts-search-v3`).
- golden-v2 training set remains the documented baseline; γ experiments branch into `data/training/experiments/2026-04-15-gamma-catalog/`.
- All ADR 009 determinism rules (per-function `random.Random(42)`).
- All ADR 013 label-scheme rules (binary + graded, MNR loss).

**Changed:**
- Phase 3 reopens (Phase 3b track under the same phase number).
- Base-model replacement is on the table for the first time since v1.

## Links

- [ADR 014](./014-gate-vs-discipline-upgrades.md) — promotion gate policy (still governs)
- [ADR 015](./015-phase-3-close-ship-v3.md) — original close; this ADR invokes its criterion 2
- [ADR 016](./016-hybrid-search-production.md) — hybrid retrieval design (the BM25-tuned baseline referenced here)
- [γ pair-mining spec](../plans/gamma-pair-mining-spec.md) — 2026-04-15
- [Base-model survey](../research/2026-04-15-base-model-survey.md) — 2026-04-15

## When this ADR is closed

When the sealed-test run executes (pass or fail). The outcome is recorded in this ADR as an addendum, and either a promotion commit or an "honest numbers" note is produced.
