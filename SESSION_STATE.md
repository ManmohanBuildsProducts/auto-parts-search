# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-14 (Phase 3 CLOSED — v3 shipped as production, ADR 015; pivoting to Phase 5)

---

## 🟢 Current focus

**Phase 3 is closed.** Production embedding is **v3** (`auto-parts-search-v3` on HF). Four further iterations (v4 A/B/C ablation + v5 queryified-YT) all failed promotion gates. ADR 015 documents the decision + learnings + when to revisit. **Pivot: Phase 5 (search API + hybrid retrieval)** starts now — the gaps v5 exposed (misspelling tolerance, part-number search) are fundamentally BM25/fuzzy problems, not embedding problems.

## ✅ Done (recent — 2026-04-13/14)

### Phase 3 wins (shipped)

- **v1.2 cleared the original +10% gate** (2026-04-13) — MRR +21.8% vs BGE-m3 on dev.
- **v3 promoted to production** (2026-04-13, ADR 014) — +4.4% over v1.2 on joint-pool graded, all 6 categories flat-or-up. Recipe: MNR + binary + batch 32 + 2 epochs + best-on-dev checkpointing + fp16 AMP + gradient checkpointing.
- **Graded benchmark infra** — `training/evaluate_graded.py` + `scripts/judge_benchmark.py` (supports multi-model joint pool); judge-model bench named DeepSeek V3 as primary (96% Claude agreement at 27× less cost than Sarvam-105B).

### Phase 3 learning experiments (discarded, ADR 015)

- **v4 ablation (A/B/C)** — raw YT hurt (−6.8%), Aksharantar carried (v4b +2.4%), Hinglish bridge hurt (v4c −2.7%). No variant cleared +10% gate.
- **v5** — queryified YT + Aksharantar + drop Hinglish. Overall −1.6% vs v3. Per-category: symptom +14% / exact_english +8% WON; misspelled −21% / part_number −53% LOST. Zero-sum at current data scale.

### Data infra built during Phase 3 (all reusable in Phase 5)

- **KG Hinglish enrichment** (306ca5d) — 2,463 KG terms × DeepSeek → Devanagari renderings. Used for Aksharantar-style bridge in training + usable as query-expansion dict in Phase 5 retrieval.
- **YouTube pilot** (053dad8) — Sarvam saarika:v2.5 STT pipeline. 13 transcripts, 109 min, 89K Hindi chars, ~$4.5 Rs 390 spent. Scripts resumable.
- **Aksharantar-AUTO filtered pairs** — 3,660 clean Roman↔Devanagari auto pairs (from ai4bharat/Aksharantar; audit-validated 84% precision at AUTO+ADJACENT). Bridge file for tokenizer.
- **LLM-judge bulk labeling** — scripts/audit_aksharantar.py + scripts/judge_benchmark.py (joint-pool, resumable).
- **Auxiliary audits** — Aksharantar precision (100-sample), YT quality read-through (3 transcripts), KG coverage gap (9% → 25.1% after enrichment).

### Memory captured

- **Regression: co-occurrence ≠ synonymy** (v1.0 catastrophic drop; fixed for v1.1+).
- **Regression: raw YT speech ≠ user query** (v4a drop; v5 addresses but costs misspelled).
- **Learning: MNR loss is unforgiving with label noise** — 18% pair noise wipes out base-model pre-training.
- **Learning: Phase 3 gate discipline pays off** — caught two structural bugs in one session for $0.
- **Feedback memories**: never trade quality silently, always save checkpoints, maximize GPU utilization (all applied in v3/v4/v5 runs).

## 🟡 In progress / partial

- (none — Phase 3 fully closed)

## 🔴 Blocked / pending external action

- **Outreach to Pikpart / AutoDukan / Parts Big Boss** — user action on own pace. v3 on HF gives us a shippable demo story now.

## 🔷 Next up (ranked by leverage)

1. **T402a — Tokenizer pipeline** (ADR 010) — IndicNLP + IndicTrans2 + lemma map. Phase 5 first step. ~4 hr.
2. **T402b — Meilisearch index + BM25 baseline** — covers misspellings + part-number search natively (the v5 regression categories). ~3 hr.
3. **T402c — Hybrid fusion (BM25 + v3 embedding) + query classifier** — the core Phase 5 deliverable. ~6 hr.
4. **T402d — Domain lemma map** (~300 entries; builds on our Hinglish bridge). ~2 hr.
5. **T401 — FastAPI `/search` endpoint** — the shippable thing to demo to prospects. ~4 hr.
6. **T400 — Qdrant vector DB** — production serving (CPU-quantized v3 + Qdrant). ~2 hr.
7. **T506 — deliver first free audit** — unchanged; highest-EV external action.

## 🗝 Key recent decisions

- **ADR 015: Phase 3 closed, v3 ships, pivot to Phase 5.** Data-only iterations hit ceiling; Phase 5 hybrid solves the misspelling/part_number gaps natively.
- **ADR 014: gate policy** — +10% for schema/loss/base changes; strict-improve-no-regressions for discipline upgrades.
- **ADR 013: binary + MNR is the v1 recipe** — CoSENT on heuristic graded labels regressed.
- **Hinglish bridge (DeepSeek-generated transliterations) is NOISE for training** — discard; still useful for query-expansion in Phase 5.
- **DeepSeek V3 is the judge model** (96% agreement with Claude at 27× less cost than Sarvam-105B).
- **Aksharantar is the only free data source that reliably helped embedding training.**
- **YouTube STT is excellent (Sarvam saarika:v2.5); YouTube *text format* is wrong for training.** Queryification helps symptom but costs misspelled.

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = verified outcome.
- **In Phase 5: misspellings and part numbers are the embedding's weak spots** — BM25 + fuzzy layer is mandatory, not optional.
- **Never use LLM-generated transliterations as training positives** — they introduce noise (v4c regression).
- **Never trade quality silently** — all lr/batch/seq/epoch/loss/base choices require explicit user approval.
- **Checkpointing + best-on-dev is the minimum discipline** for any training run going forward.
- `TASKS.md` is the single task-board source.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds.
- **Claude starting a session:** auto-injected via `~/.claude/hooks/session-state.sh`. Also `/status`.
- **Claude ending a session:** `/wrap` — updates this file + proposes commits.
