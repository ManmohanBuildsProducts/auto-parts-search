# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-13 (T110b shipped — ITI v2 wired into graph.db; Phase 2b 100% complete)

---

## 🟢 Current focus

**Phase 2b 100% complete.** graph.db now reflects the ITI v2 dataset (4,252 nodes / 5,445 edges — +62% vs v1). GTM tools ready (notebook + 5 named prospects). Phase 3 (training loop) is the next phase — first Phase-3 task is T303a (`training/evaluate.py` harness).

## ✅ Done (recent — 2026-04-12/13, 16 commits)

- **T110b — ITI v2 wired into graph.db (a99f83c)** — `build_graph.py:ingest_iti_v2` reads merged systems + diagnostics + aliases with provenance. Graph: 2,627 → 4,252 nodes (+62%), 3,375 → 5,445 edges (+61%). Big wins: aliases 189 → 1,111 (+922 Hindi/Hinglish vocabulary), parts 1,584 → 2,121 (+537), symptoms 103 → 247 (+144). Query-layer tests pass: "patti" returns brake_pad + brake_lining + leaf_spring; `alias:kicker → part:kick_starter`.
- **HF Datasets raw snapshot (f957e95)** — `scrape-v3-2026-04-13` uploaded to `ManmohanBuildsProducts/auto-parts-search-raw` (private), 21MB tarball (516MB raw), SHA-verified round-trip via `scripts/fetch_raw.sh`. Reproducibility chain complete.
- **v1+v2 ITI merge (f05771d)** — `scripts/merge_iti_v2.py` folds hand-curated v1 (124 parts / 103 chains) into v2 via `provenance.method`. Final: 646 parts (86 dual-sourced) / 247 chains (10 dual-sourced). 93 v1-only diagnostics preserved.
- **Scraping queue (f05771d)** — `context/scraping-queue.md` evergreen domain registry.

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

1. **T506 — deliver first free audit** — run `notebooks/search_audit.ipynb` against one prospect's catalog. Requires LinkedIn DM to Ratan Kumar Singh (Pikpart) / Pranay Tagare (AutoDukan) / Vineet Asija (Parts Big Boss). **Highest-EV item; retires the single biggest unknown in the project.** At the user's own pace.
2. **T303a — `training/evaluate.py` harness** — opens Phase 3. `evaluate(model_path, benchmark_path) → {mrr, ndcg@10, recall@5, zero_result_rate}`. Baseline with `all-MiniLM-L6-v2`. ~30 min.
3. **T208 + T208b — benchmark dev/test split + top-20 graded labels via LLM judge** — unblocks nDCG@10. ~1.5 hr.
4. **T303b — base-model shootout** — BGE-m3, Jina v3, multilingual-e5-large, OpenAI `text-embedding-3-large`, Cohere `embed-multilingual-v3` on our 195-query benchmark. Decide base for fine-tuning. ~2 hr.
5. **T112 — Boodmo → HSN category mapping (top 1K parts)** — enriches KG for Phase 3 pair generation. ~2 hr.
6. **T200b + T201b + T202b — generate pair sets from the merged KG** — HSN hierarchy graded pairs, ITI system-membership pairs, diagnostic chain pairs. Phase 3 training loop unit-of-work. ~3 hr total.

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
