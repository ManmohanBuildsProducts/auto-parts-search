# Session 2026-04-12 — Approved tasks vs. actual delivery

Direction decided + tasks queued + what actually shipped.

---

## Direction decisions made (ADRs)

| ADR | Decision | Rationale in one line |
|-----|----------|----------------------|
| 005 | Markdown is the single task-board source. Delete Cline Kanban JSON. | Dual sources always drift (evidence: 7+ completed Phase 2 tasks silently undrifted). |
| 006 | Collapse Phase 3 + Phase 4 into one training loop. Atomic unit = `(pair_strategy, model, benchmark)` triple. | Open-loop pair gen produced 4 discarded tasks (T200/T201/T202/T206). |
| 007 | Knowledge graph stored in SQLite. JSON files = inputs, .db = derived, gitignored. | 2,627 nodes → 100K nodes after Boodmo-HSN mapping; JSON traversal is O(N). |
| 008 | Disclose: `iti_*.json` is v1 hand-curated, not PDF-extracted. Plan v2 LLM extraction. | Audit found 95% of content is hardcoded Python dicts. |
| 009 | Reproducibility: snapshot + `random.seed(42)` + `golden/experiments/` directory split. | Benchmark and pairs currently non-deterministic; unverifiable to a prospect. |
| 010 | Search tokenizer = IndicNLP + IndicTrans2 + ~300-entry lemma map. Meilisearch over Typesense. | Off-the-shelf BM25 tokenizers all break on Hindi-Latin code-mixed text. |
| 011 | Stay vertical (auto parts). Reposition as "Indian multilingual commerce search." Move GTM (T505/T506a) forward. | Market research: Algolia zero Hindi, Klevu complaint = cost, ONDC is open. Solo founder cannot win horizontal. |

---

## Task ledger

### Track A — SQLite migration (ADR 007)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T113a | `auto_parts_search/graph_db.py` | ✅ | ✅ | GraphDB class; 7 query helpers; FTS5 |
| T113b | `scripts/build_graph_db.py` | ✅ | ✅ | Idempotent rebuild; not yet executed against real data |
| T113c | `tests/test_graph_db.py` | ✅ | ✅ | 7/7 tests pass |
| T113d | CLI `build-graph-db` | ✅ | ✅ | Wired in `__main__.py`; not yet run |
| T113-verify | Run against real graph, verify counts | — | ❌ | 15 min, not done |

### Track B — ITI re-extraction (ADR 008)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T101b-unblock | Remove `*.pdf` from .gitignore for iti_pdfs/ | ✅ | ✅ | `.gitignore` updated |
| T101b-fetch | Download + commit 6 DGT PDFs | ✅ | ❌ | 10 min network call, not done |
| T102b | LLM-extract parts per system with provenance | ✅ | ❌ | Largest unfinished piece; 2-3 hr |
| T103b | LLM-extract diagnostic chains with provenance | ✅ | ❌ | Paired with T102b |
| T102c | Public-framing update in PRODUCT.md + decisions/003 | ✅ | ❌ | 15 min, not done — still overclaims |
| N/A | Audit ASDC/HSN/NHTSA for same pattern | ✅ (blanket) | ❌ | Offered; not executed |

### Track C — Reproducibility (ADR 009)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T603a | `random.seed(42)` in `training/*.py` | ✅ | 🟡 | Added to `catalog_pairs.py` at module level (weaker than `Random(seed)`); `vocabulary_pairs.py` already had it; `benchmark.py` doesn't use random |
| T603b | `data/raw/MANIFEST.md` + first entry | ✅ | 🟡 | Template with TBD placeholders; no real SHA256 |
| T603c | Backblaze B2 upload | ✅ | ❌ | Needs credentials |
| T603d | `scripts/fetch_raw.py` | ✅ | ❌ | Not written |
| T603e | Move `*.jsonl` to `golden/` | ✅ | ❌ | Deferred until determinism verified |
| T603-verify | Run pair-gen twice, diff to verify determinism | — | ❌ | 10 min, not done |

### Track D — Housekeeping (ADR 005)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T604 | Delete `cline-kanban-board.json` | ✅ | ✅ | `git rm` staged (not yet committed) |
| T605 | Reconcile TASKS.md with git reality | ✅ | ✅ | Rewritten with commit hashes in Done section |

### Track E — Decisions + plans (ADRs + planning docs)

| Deliverable | Approved | Shipped |
|-------------|---------|---------|
| ADR 005 task-board-markdown | ✅ | ✅ |
| ADR 006 phase3-training-loop | ✅ | ✅ |
| ADR 007 kg-sqlite-storage | ✅ | ✅ |
| ADR 008 iti-provenance | ✅ | ✅ |
| ADR 009 reproducibility | ✅ | ✅ |
| ADR 010 search-tokenizer | ✅ | ✅ |
| ADR 011 positioning-moat | ✅ | ✅ |
| Plan: phase3-training-loop.md | ✅ | ✅ |
| Plan: phase2b-cleanup.md | ✅ | ✅ |
| TASKS.md rewrite | ✅ | ✅ |
| memory/regressions.md | ✅ | ✅ |
| context/research/market-audit-2026-04-12.md | ✅ | ✅ |

### Track F — GTM unblock (ADR 011 recommendation)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T505 | Identify 5 target mid-market Indian prospects | ✅ (blanket) | ❌ | Not started |
| T506a | Notebook audit skeleton | ✅ (blanket, recommended) | ❌ | **Highest-leverage missed item** |

### Track G — Session hygiene

| Item | Approved | Shipped |
|------|---------|---------|
| Commit the session (per-cluster commits) | ✅ (implicit) | ❌ | All unstaged |
| Fix `test_iti_scraper::test_minimum_100_chains` (xfail) | — | ❌ |

---

## Raw counts

| Category | Approved items | Shipped | Partial | Missed |
|----------|---------------|---------|---------|--------|
| ADRs + plans + docs | 12 | 12 | 0 | 0 |
| SQLite migration (Track A) | 5 | 4 | 0 | 1 |
| ITI re-extraction (Track B) | 6 | 1 | 0 | 5 |
| Reproducibility (Track C) | 6 | 0 | 2 | 4 |
| Housekeeping (Track D) | 2 | 2 | 0 | 0 |
| GTM unblock (Track F) | 2 | 0 | 0 | 2 |
| Session hygiene (Track G) | 2 | 0 | 0 | 2 |
| **Total** | **35** | **19** | **2** | **14** |

**Completion ratio:** 19/35 fully shipped = 54%. With partials counted at 0.5 → 20/35 = 57%.

---

## Next steps, ranked by leverage

1. **T506a notebook audit skeleton** (1 hr) — only item that retires business risk
2. **T101b fetch + commit PDFs** (10 min) — unblocks LLM extraction
3. **T113-verify: run `build-graph-db` against real graph** (15 min) — proves ADR 007
4. **T102b/T103b LLM re-extraction** (2-3 hr) — kills provenance risk, rebalances 2W
5. **ASDC/HSN/NHTSA parser audit** (30 min) — is the hand-curation pattern repeated?
6. **T603-verify + T603e: verify determinism + promote to golden/** (20 min)
7. **T603a upgrade to `Random(seed)` pattern** (10 min) — robustness
8. **T102c public framing update** (15 min) — truth-in-labeling
9. **xfail the failing ITI test** (5 min) — green CI
10. **Commit the session** (10 min, multiple focused commits) — baseline for above

Work items 1-3 in one focused next session = ~90 minutes; retires the two biggest risks (GTM unknown + SQLite unverified + provenance) simultaneously.
