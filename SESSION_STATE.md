# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-13 (Phase 3 first training loop landed — v1.2 beats BGE-m3 base by +21.8% MRR / +38% graded nDCG@10 on dev-149)

---

## 🟢 Current focus

**Phase 3 first training loop complete end-to-end.** Closed the loop from pair generation → HF upload → Colab fine-tune → HF model push → local benchmark → graded re-eval. After two bad runs exposed label-schema bugs, v1.2 cleared the gate on the third attempt. Golden v2 promoted. Ready for Phase 3 track B (graded-label training with CoSENT loss) or jump to Phase 5 (search API).

## ✅ Done (recent — 2026-04-13, Phase 3 session)

- **T303a — evaluate.py harness (63cf909)** — CLI `python3 -m training.evaluate`. MRR / nDCG@10 / Recall@5 / zero-result-by-type against KG corpus (option 1, 2,121 parts). MiniLM baseline: MRR 0.397.
- **T303b Stage A — open-weights shootout (3282d67)** — BGE-m3, e5-large (with prefix support), MiniLM. Decision: fine-tune on BGE-m3 (balanced; T4-friendly). Jina v3 skipped (broken transitive dep on Mac CPU). ADR 012 unchanged.
- **T208 — dev/test split (599fbf1)** — `scripts/split_benchmark.py`, seed 42, 149 dev / 46 sealed test, stratified by query_type.
- **T201b + T202b — KG pair generators (c284532)** — ITI system membership + diagnostic chains, with alias expansion. 2,902 + 4,556 pairs.
- **T200b — HSN graded pairs (807c529)** — sibling (0.85) + cousin (0.40) pairs from HSN hierarchy, 1,753 pairs.
- **T302 — Colab training notebook + HF pair upload (8538881)** — `notebooks/train_v1.ipynb` + `scripts/upload_pairs_to_hf.py`. Batch 16 / seq 128 / fp16 AMP fits T4 (00f6044). Idempotent push via `HfApi.upload_folder` (2d9bc06).
- **🎯 v1.2 fine-tune cleared the Phase 3 gate (b3cca6e)** — MRR 0.468 vs BGE-m3 base 0.384 on dev-149 = **+21.8%** (bar: +10%). Per-category gains (zero-result rate):
  - Hindi/Hinglish 40.7% → **29.6%** (−27%)
  - Symptom 55.6% → **40.7%** (−27%)
  - Brand-as-generic 63.6% → **45.5%** (−28%)
- **🎯 golden-v2 promoted (b3cca6e)** — `data/training/golden/all_pairs_v2.jsonl` (26,760 pairs, SHA `7157b634…`). METADATA updated with v1.2 as first model to clear the gate.
- **T208b — DeepSeek V3 graded labels (6166a85 + d4db804)** — 149 dev queries × top-20 candidates = 2,980 judgments, 0/1/2 graded. `training/evaluate_graded.py` re-scores against this pool:
  - Graded nDCG@10: BGE-m3 0.400 → v1.2 **0.554** (**+38.4%**)
  - Graded Recall@5: BGE-m3 0.433 → v1.2 **0.485** (+12.0%)
  - Per-type: hindi_hinglish +57%, symptom +68%, brand_as_generic +48%, exact_english +26%, misspelled +21%, part_number tied (both ~0.11 — embedding-inappropriate task, needs Phase 5 hybrid).

**Note on failed runs (kept as learnings, not artifacts):**
- v1.0 regressed −10.6% due to co-occurrence pairs labeled 1.0 (catastrophic conflation). Fix in `95000f1` — grade cooccurrence at 0.5.
- v1.1 still −2.4% — catalog positives over-broad. Fix in `8d57414` — filter catalog by group-key specificity (drop 1-part brand-only, downgrade 2-part to 0.5).
- Both documented in `memory/learnings.md` → "Training / Embeddings".

## 🟡 In progress / partial

- (none — every task in this session landed)

## 🔴 Blocked / pending external action

- **Outreach to Pikpart / AutoDukan / Parts Big Boss** — user action on own pace; pitch + audit notebook still ready.
- **Pool-bias fix for external benchmarks (T305)** — graded pool was retrieved by v1.2, biasing comparison to v1.2's advantage. Fix = union top-20s from multiple models before judging. Needed before OpenAI/Cohere comparison.

## 🔷 Next up (ranked by leverage)

1. **T506 — deliver first free audit** — unchanged from last session; highest-EV single item. At user's pace.
2. **T303c — pair schema ADR 013 (binary vs graded)** — 1-epoch CoSENT training run on the graded labels, compare vs MNR v1.2. Decide the v2 loss function. ~1 hr.
3. **T303d — loss function ADR 014** — follows T303c. Likely CoSENT (graded) + MultipleNegatives (distill). ~30 min doc.
4. **T303e — v2 training run** — same base (BGE-m3), graded labels, CoSENT loss. Must beat v1.2 by ≥10% graded nDCG@10 to promote. ~1 hr Colab + bench.
5. **T305 — OpenAI / Cohere external benchmark** — needs joint pool + paid API keys. ~$1 spend. Ships the "credible vs incumbents" number. Bar: v2 ≥ OpenAI on Hindi subset or stop fine-tuning path.
6. **Phase 5 kickoff** — T402a tokenizer / T401 FastAPI. Needed regardless of Phase 3 outcome for shipping.

## 🗝 Key recent decisions

- **Co-occurrence is not synonymy.** Cooccurrence pairs grade at 0.5, membership + symptom_part stay at 1.0. Logged in `memory/learnings.md`.
- **Catalog positives filtered by group-key specificity** — 3-part (cat+brand+model) = 1.0; 2-part (brand+model) = 0.5; 1-part (brand only) dropped. `scripts/merge_v2_pairs.py`.
- **Phase 3 gate discipline pays off** — when v1 failed the gate, plan said "don't tune hyperparameters, fix data." Doing that caught two structural bugs in one session at ~$0 cost.
- **Part-number retrieval is not an embedding problem** — both BGE-m3 and v1.2 score ~0.11 nDCG@10 on part_number queries. Phase 5 hybrid search (BM25 fusion) is the fix, not more fine-tuning.
- **golden-v2 locked** — `all_pairs_v2.jsonl` SHA `7157b634…` is the new training baseline. Future pairs work branches into `data/training/experiments/` and only promotes on a proven beat-v1.2 run.

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = verified outcome (`memory/regressions.md`).
- Phase 3 gate rule: **if a trained model fails +10% on dev MRR, stop — fix data, don't tune hyperparameters.**
- `TASKS.md` is the single task-board source.
- CLAUDE.md stays <100 lines / 2,500 tokens. Architecture → skills. Decisions → ADRs.
- Experiments live in `data/training/experiments/`; never mutate `golden/` directly except via a promotion commit.
- Pool-bias in graded nDCG@10: current scores favor the model whose top-20 seeded the judge. Fix before external benchmarks.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds. You know where we are.
- **Claude starting a session:** auto-injected via `~/.claude/hooks/session-state.sh`. Also `/status`.
- **Claude ending a session:** `/wrap` — updates this file + proposes commits.
- **If stale:** `/status` to refresh from git log + TASKS.md.
