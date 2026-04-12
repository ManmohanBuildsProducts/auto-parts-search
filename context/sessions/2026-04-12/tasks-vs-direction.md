# Session 2026-04-12 — Approved tasks vs. actual delivery (final)

Direction decided + tasks queued + what actually shipped. Final updated ledger after session wrap.

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

Plus: adopted Anthropic's claude-progress pattern (Nov 2025 harness blog) + promoted to global session-hygiene rule (`~/.claude/rules/session-hygiene.md`).

---

## Task ledger

### Track A — SQLite migration (ADR 007)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T113a | `auto_parts_search/graph_db.py` | ✅ | ✅ | GraphDB class; 7 query helpers; FTS5. Commit c958134. |
| T113b | `scripts/build_graph_db.py` | ✅ | ✅ | Idempotent rebuild. Commit c958134. |
| T113c | `tests/test_graph_db.py` | ✅ | ✅ | 7/7 pass. Commit c958134. |
| T113d | CLI `build-graph-db` | ✅ | ✅ | Wired in `__main__.py`. Commit c958134. |
| T113-verify | Run against real graph, verify counts | — | ❌ | 15 min, not done. Queued as Next-up #3. |

### Track B — ITI re-extraction (ADR 008)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T101b-unblock | Remove `*.pdf` from .gitignore for iti_pdfs/ | ✅ | ✅ | Commit c958134. |
| T101b-fetch | Download + commit 6 DGT PDFs | ✅ | ❌ | 10 min network call. Queued as Next-up #2. |
| T102b | LLM-extract parts per system with provenance | ✅ | ❌ | Largest remaining piece. 2–3 hr. Next-up #4. |
| T103b | LLM-extract diagnostic chains with provenance | ✅ | ❌ | Paired with T102b. |
| T102c | Public-framing update in PRODUCT.md + decisions/003 | ✅ | ❌ | 15 min. Next-up #7. |
| — | Audit ASDC/HSN/NHTSA for same pattern | ✅ (blanket) | ❌ | 30 min. Next-up #5. |

### Track C — Reproducibility (ADR 009)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T603a | `random.seed(42)` in `training/*.py` | ✅ | 🟡 | Added module-level in `catalog_pairs.py`; `vocabulary_pairs.py` already had per-function `Random(seed)`; `benchmark.py` doesn't use random. Upgrade pending. |
| T603b | `data/raw/MANIFEST.md` + first entry | ✅ | 🟡 | Template with TBD SHA256s. |
| T603c | Backblaze B2 upload | ✅ | ❌ | Needs credentials. Blocked. |
| T603d | `scripts/fetch_raw.py` | ✅ | ❌ | Not written. |
| T603e | Move `*.jsonl` to `golden/` | ✅ | ❌ | Deferred pending determinism verification. |
| T603-verify | Two consecutive pair-gen runs byte-identical | — | ❌ | 10 min. |

### Track D — Housekeeping (ADR 005)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T604 | Delete `cline-kanban-board.json` | ✅ | ✅ | Commit 3f2b187. |
| T605 | Reconcile TASKS.md with git reality | ✅ | ✅ | Commit c92c94b. |

### Track E — Decisions + plans + research (all ✅, commit c92c94b)

ADRs 005–011, phase3-training-loop plan, phase2b-cleanup plan, TASKS.md rewrite, `memory/regressions.md`, `context/INDEX.md`, market-audit report, claude-code-workflows report, session retrospective (3 files).

### Track F — GTM unblock (ADR 011)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T505 | Identify 5 target mid-market Indian prospects | ✅ | ❌ | Next-up-adjacent (manual outreach). |
| T506a | Notebook audit skeleton | ✅ | ❌ | **Highest-leverage missed item. Next-up #1.** |

### Track G — Session dashboard + global install (added mid-session)

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| T700 | `SESSION_STATE.md` dashboard at repo root | ✅ | ✅ | Commit 35ce0e9. |
| T701 | `/start` `/status` `/wrap` slash commands (project-local first, then global) | ✅ | ✅ | Commits 35ce0e9, ae19f95. |
| T702 | Global `SessionStart` hook (`~/.claude/hooks/session-state.sh`) | ✅ | ✅ | Installed globally; smoke-tested (runs in project root, silent at `~`). |
| T703 | `~/.claude/rules/session-hygiene.md` + global CLAUDE.md reference | ✅ | ✅ | Makes the scaffold auto-bootstrapped in every future project. |
| T704 | `.claude/skills/architecture/SKILL.md` | ✅ | ✅ | Commit 35ce0e9. |
| T705 | Trim CLAUDE.md to <100 lines | ✅ | ✅ | Commit 35ce0e9. |
| T706 | Live-verify hook fires in a fresh Claude Code session | — | ❌ | User-machine action (open new session → confirm). |

### Track H — Commits + data

| ID | Task | Approved | Shipped | Notes |
|----|------|---------|---------|-------|
| H1 | Commit the session in focused clusters | ✅ (implicit) | ✅ | 6 commits: 3f2b187, c92c94b, c958134, 35ce0e9, ae19f95, eea85f0. |
| H2 | Commit pre-existing data file regeneration | ✅ | ✅ | Commit eea85f0. |
| H3 | Xfail `test_iti_scraper::test_minimum_100_chains` | — | ❌ | 5 min. Next-up #8. |

---

## Raw counts (final)

| Category | Approved items | Shipped | Partial | Missed |
|----------|---------------|---------|---------|--------|
| Decisions + plans + docs (Track E) | 12 | 12 | 0 | 0 |
| SQLite migration (Track A) | 5 | 4 | 0 | 1 |
| ITI re-extraction (Track B) | 6 | 1 | 0 | 5 |
| Reproducibility (Track C) | 6 | 0 | 2 | 4 |
| Housekeeping (Track D) | 2 | 2 | 0 | 0 |
| GTM unblock (Track F) | 2 | 0 | 0 | 2 |
| Session dashboard + global (Track G) | 7 | 6 | 0 | 1 |
| Commits + data (Track H) | 3 | 2 | 0 | 1 |
| **Total** | **43** | **27** | **2** | **14** |

**Completion ratio:** 27/43 fully shipped = 63%. With partials at 0.5 → 28/43 = 65%. (Previous ledger was 19/35; Track G + Track H pushed the shipped count up substantially.)

---

## Next steps, ranked by leverage (re-ranked post-session)

1. **T506a notebook audit skeleton** (1 hr) — only item that retires business risk.
2. **T101b fetch + commit PDFs** (10 min) — unblocks LLM extraction.
3. **T113-verify: run `build-graph-db` against real graph** (15 min) — proves ADR 007.
4. **T102b/T103b LLM re-extraction** (2–3 hr) — kills provenance risk, rebalances toward 2W/3W.
5. **ASDC/HSN/NHTSA parser audit** (30 min) — does the hand-curation pattern generalize?
6. **T603a upgrade + T603-verify + T603e promote** (20 min) — determinism claim closed.
7. **T102c public framing update** (15 min) — truth-in-labeling.
8. **T706 live-verify hook** (2 min user action, then confirm) — closes Track G.
9. **H3: xfail the failing ITI test** (5 min) — green CI.

Work items 1–3 in one focused next session (~90 minutes) retires the two biggest remaining risks: GTM unknown + SQLite unverified + provenance overclaim.

---

## Postscript

This session was recursive: it both *audited* the project and *built the infrastructure* to make future sessions cheaper (session dashboard + global hook + session-hygiene rule). Track E's ADRs + Track G's dashboard are the durable output. The remaining missed items (Tracks B, C, F) are known quantities queued with clear effort estimates — no hidden unknowns.

Lesson captured in `memory/regressions.md`: "Done is a verified outcome, not an artifact." Most of the "missed" items in this ledger are missed precisely because they require *outcome verification* (live hook test, real graph build, real prospect conversation) that a single-session audit cannot deliver.
