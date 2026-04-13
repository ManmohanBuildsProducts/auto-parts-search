# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-13 (Phase 2b fully shipped — HF Datasets snapshot closes reproducibility chain)

---

## 🟢 Current focus

Phase 2b fully shipped except one follow-up (T110b: integrate ITI v2 into `build_graph.py`). GTM is now materially unblocked — first prospect list + audit notebook are ready. Next session = T110b integration + deliver first audit to one of the 3 top prospects.

## ✅ Done (recent — 2026-04-12/13, 13 commits)

- **HF Datasets raw snapshot (f957e95)** — `scrape-v3-2026-04-13` uploaded to `ManmohanBuildsProducts/auto-parts-search-raw` (private), 21MB tarball (516MB raw), SHA-verified round-trip via `scripts/fetch_raw.sh`. T603b/c/d all closed. Reproducibility chain complete.
- **v1+v2 ITI merge (f05771d)** — `scripts/merge_iti_v2.py` now folds hand-curated v1 (124 parts / 103 chains) into v2 via `provenance.method`. Final: 646 parts (86 dual-sourced) / 247 chains (10 dual-sourced). 93 v1-only diagnostics preserved.
- **Scraping queue (f05771d)** — `context/scraping-queue.md` as evergreen registry for domains × (scrape status + outreach status + priority).

- **ITI v2 LLM extraction (a4eb69d)** — 6 parallel subagents parsed DGT PDFs + `scripts/merge_iti_v2.py` consolidated:
  - 20 systems / 608 parts (5× v1) / 154 diagnostics / **168 aliases** — all with `source_page` citations.
  - Alias goldmine: `kicker`, `chain patta`, `brake patti`, `tanki`, `hawa filter`, `shocker`, `kamani`, `chaabi`, `tayar`, `teeli`, `self`, `dynamo`, `hooter`, `dipper`, `silencer`, `dickey`, and more.
  - Provenance on every leaf: `{method: "llm_extracted", trade, pdf, page}`.
- **T505 prospects (a4eb69d)** — 5 pilot candidates named, top 3: **Pikpart** (Faridabad 2W, blank-slate search), **AutoDukan** (Pune, $1.36M raised), **Parts Big Boss** (Ghaziabad, GoDaddy+Zoho stack). Full report at `context/research/t505-prospects-2026-04-12.md`.
- **Phase 2b execution (775e446)** — PDFs committed, T113-verify, T603a/verify/e, T102c framing, notebook skeleton.
- **Session dashboard + global install (35ce0e9, ae19f95)** — `SESSION_STATE.md`, `/start`/`/status`/`/wrap` global commands, SessionStart hook.
- **SQLite KG (c958134)** — `graph_db.py` + 7 tests + `build-graph-db` CLI.
- **Phase 2b scaffolding (c92c94b)** — ADRs 005–011, 2 plans, market + workflow research.
- **Cline Kanban removed (3f2b187)**.

## 🟡 In progress / partial

- (none — all Phase 2b tasks shipped)

## 🔴 Blocked / pending external action

- **Outreach to Pikpart / AutoDukan / Parts Big Boss** — user action on their own pace; pitch copy + audit notebook ready when they are.

*(T706 hook live-verify ✅ confirmed in a fresh session 2026-04-13 — SessionStart hook auto-injects SESSION_STATE + commits + regressions, briefing correctly names next-up items. Cline extension disable ✅ deferred at user's discretion, not a project blocker.)*

## 🔷 Next up (ranked by leverage)

1. **T506 — deliver first free audit** — run `notebooks/search_audit.ipynb` against one prospect's catalog. Requires LinkedIn DM to Ratan Kumar Singh (Pikpart) / Pranay Tagare (AutoDukan) / Vineet Asija (Parts Big Boss) asking for 48 hrs of search logs. **Highest-EV item; retires the single biggest unknown in the project.**
2. **T110b — integrate ITI v2 into `build_graph.py`** — currently graph.db uses v1 hand-curated. Update to prefer v2, or merge both with provenance-marked nodes. Rebuild graph.db. Expected count: v1 2,627 → v2 ~3,200+ nodes. ~30 min.
3. **T208 + T208b — benchmark dev/test split + top-20 graded labels** — unblocks Phase 3 nDCG@10 measurement. ~1.5 hr.
4. **T603b/c — MANIFEST SHA256s + Backblaze upload** — closes reproducibility chain. ~30 min (once B2 account exists).
5. **T112 — Boodmo → HSN category mapping for top 1K parts** — enriches KG for Phase 3. ~2 hr.
6. **T303a — `training/evaluate.py` harness** — the `(model, benchmark) → scores` function. ~30 min.

## 🗝 Key recent decisions

- **ITI v2 is LLM-extracted with page citations** — disclosure obligation from ADR 008 discharged; PRODUCT.md + decisions/003 already reflect honest v1 hand-curated framing.
- **2W/3W vocabulary is concentrated in the 2W syllabus** — 57 aliases from one PDF. Hindi-belt mechanic terms are extractable from this source; future models should weight 2W/3W highly.
- **Stay vertical, Indian multilingual commerce search** — ADR 011.
- **Phase 3 = training loop** — `(pair_strategy, model, benchmark)` triples — ADR 006.
- **SQLite for KG** — ADR 007. graph.db is 3.3MB; will grow with T110b.
- **Session-hygiene as global rule** — `~/.claude/rules/session-hygiene.md`.

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = verified outcome (`memory/regressions.md`).
- Do NOT generate training pairs without a model to consume them (ADR 006; T200-T206 post-mortem).
- `TASKS.md` is the single task-board source.
- CLAUDE.md stays <100 lines / 2,500 tokens. Architecture → skills. Decisions → ADRs.
- Experiments live in `data/training/experiments/`; never mutate `golden/` directly.
- v1 and v2 ITI files both exist; the graph currently reads v1. Integration via T110b is the next gate.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds. You know where we are.
- **Claude starting a session:** auto-injected via `~/.claude/hooks/session-state.sh`. Also `/status`.
- **Claude ending a session:** `/wrap` — updates this file + proposes commits.
- **If stale:** `/status` to refresh from git log + TASKS.md.
