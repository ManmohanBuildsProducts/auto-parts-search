# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-12 (audit + Phase 2b scaffolding + session dashboard setup)

---

## 🟢 Current focus

Phase 2b cleanup tracks + GTM unblock (per ADR 011). No active coding task; next session will pick from "Next up" below.

## ✅ Done (recent)

- **ADRs 005–011 committed** — task-board markdown, Phase 3+4 collapse, SQLite KG, ITI provenance, reproducibility, search tokenizer, positioning.
- **SQLite KG migration** — `auto_parts_search/graph_db.py` + `scripts/build_graph_db.py` + 7 passing tests (ADR 007).
- **Session dashboard installed** — this file + `/status` / `/wrap` / `/start` slash commands + architecture skill.
- **CLAUDE.md trimmed** — architecture details moved to `.claude/skills/architecture/`.
- **Cline Kanban deprecated** — `context/cline-kanban-board.json` removed (ADR 005); user to uninstall the Cline extension.
- **Market research** — `context/research/market-audit-2026-04-12.md` (key finding: Algolia has zero Hindi NLP; stay vertical per ADR 011).
- **Claude Code workflow research** — `context/research/claude-code-workflows-2026-04-12.md` (Anthropic harness pattern drives this dashboard).

## 🟡 In progress / partial

- **Catalog pair determinism** — `random.seed(RANDOM_SEED)` added at module level in `training/catalog_pairs.py`. Weaker than per-function `Random(seed)`; upgrade pending.
- **Golden training set** — `data/training/golden/{README,METADATA}.md` scaffolded but current `data/training/*.jsonl` NOT moved in (waiting for determinism verification: 2 consecutive runs must produce byte-identical output).
- **SQLite build** — code + unit tests complete, but `python3 -m auto_parts_search build-graph-db` not yet run against the real 2,627-node graph. Needs 15 min to smoke-test.

## 🔴 Blocked / pending external action

- **T603c Backblaze B2 upload** — awaits B2 credentials.
- **Cline VS Code extension disable** — user-machine action; Claude can't do it.
- **Settings.json SessionStart hook** — `.claude/settings.local.json` written but not verified (needs fresh session to fire).

## 🔷 Next up (ranked by leverage)

1. **T506a notebook audit** — Jupyter notebook using OpenAI `text-embedding-3-large` to rerank one prospect's CSV. Unblocks GTM (ADR 011's primary recommendation). ~1 hr. **Single highest-EV item in the project.**
2. **T101b — fetch + commit 6 DGT PDFs** — `.gitignore` already allows; just need the download + commit. ~10 min.
3. **T113-verify — run `build-graph-db` against real graph** — confirms ADR 007 end-to-end. ~15 min.
4. **T102b/T103b — LLM re-extract ITI content** — kills the provenance risk (ADR 008) + rebalances toward 2W/3W. ~2–3 hr.
5. **ASDC/HSN/NHTSA parser audit** — is the ITI hand-curation pattern repeated elsewhere? ~30 min.
6. **T603a upgrade + T603-verify + T603e promote** — per-function `rng = Random(42)`, verify determinism, move files into `golden/`. ~20 min.
7. **T102c public framing update** — PRODUCT.md + decisions/003 — disclose v1 hand-curation. ~15 min.
8. **Xfail `test_iti_scraper::test_minimum_100_chains`** — green CI; link to T103b. ~5 min.

## 🗝 Key recent decisions

- **Stay vertical (auto parts).** Market research confirmed the horizontal pivot loses for a solo founder; Algolia gap in Hindi is the real wedge (ADR 011).
- **Collapse Phase 3 + 4.** Unit of work = `(pair_strategy, model, benchmark)` triple, not a data file (ADR 006).
- **SQLite for KG.** JSON stays as committed input; `.db` is derived + gitignored (ADR 007).
- **ITI content is hand-curated v1.** Disclose publicly; LLM re-extract in Phase 2b (ADR 008).

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = measured outcome (see `memory/regressions.md`).
- Do NOT generate training pairs without a model to consume them. Open-loop Phase 3 burned a week.
- `TASKS.md` is the single task-board source. Never introduce a parallel tool-state board.
- CLAUDE.md stays under ~100 lines. Put architecture in skills, decisions in ADRs.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds. You know where we are.
- **Claude starting a session:** should be auto-injected via `SessionStart` hook in `.claude/settings.local.json`. Also available via `/status` command.
- **Claude ending a session:** run `/wrap`. Updates this file + offers commit.
- **If this is stale:** run `/status` to refresh from git log + TASKS.md.
