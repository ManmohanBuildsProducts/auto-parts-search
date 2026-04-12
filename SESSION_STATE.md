# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-12 (audit + Phase 2b scaffolding + session dashboard setup + global promotion)

---

## 🟢 Current focus

Phase 2b cleanup tracks + GTM unblock (per ADR 011). No active coding task; next session picks from "Next up" below. All foundational scaffolding shipped.

## ✅ Done (recent)

- **6 session commits on master** — kanban deletion, audit docs, SQLite code, dashboard scaffold, global command promotion, data files.
- **ADRs 005–011 committed** — task-board markdown, Phase 3+4 collapse, SQLite KG, ITI provenance, reproducibility, search tokenizer, positioning.
- **SQLite KG migration** — `auto_parts_search/graph_db.py` + `scripts/build_graph_db.py` + 7 passing tests (ADR 007). Smoke test against real graph pending.
- **Session dashboard** — `SESSION_STATE.md` + `/start` / `/status` / `/wrap` commands + `architecture` skill.
- **Global promotion** — `/start` `/status` `/wrap` now live at `~/.claude/commands/`; SessionStart hook at `~/.claude/hooks/session-state.sh` (smoke-tested: auto-loads in any project with `SESSION_STATE.md`, silent otherwise). Project-local duplicates removed.
- **Global session-hygiene rule** — `~/.claude/rules/session-hygiene.md` baked into `~/.claude/CLAUDE.md`. Claude now auto-bootstraps the canonical file set (SESSION_STATE, TASKS, memory, ADRs, plans) in any new project without prompting.
- **CLAUDE.md trimmed** — under 100 lines; architecture in `.claude/skills/architecture/`.
- **Cline Kanban deprecated** — `context/cline-kanban-board.json` removed and committed (ADR 005). User still to disable the VS Code extension.
- **Data files committed** — pre-existing `all_pairs.jsonl` + `catalog_pairs.jsonl` regeneration flushed; clean working tree except the two below in "In progress".
- **Market research** — `context/research/market-audit-2026-04-12.md` (Algolia zero Hindi NLP; stay vertical).
- **Claude Code workflow research** — `context/research/claude-code-workflows-2026-04-12.md` (Anthropic harness pattern drives this dashboard).

## 🟡 In progress / partial

- **Catalog pair determinism** — `random.seed(RANDOM_SEED)` at module level in `training/catalog_pairs.py`; should upgrade to per-function `rng = Random(42)` for robustness.
- **Golden training set** — `data/training/golden/{README,METADATA}.md` scaffolded but `*.jsonl` NOT moved in (waiting on determinism verification: two consecutive runs byte-identical).
- **SQLite build** — unit tests pass; `python3 -m auto_parts_search build-graph-db` not yet run against the real 2,627-node graph. 15 min smoke test pending.
- **MANIFEST.md** — template with TBD SHA256s; awaits Backblaze B2 upload.

## 🔴 Blocked / pending external action

- **T603c Backblaze B2 upload** — awaits B2 credentials from user.
- **Cline VS Code extension disable** — user-machine action; JSON is gone from repo, but the extension may still be running locally.
- **SessionStart hook live-verification** — needs the user to open a fresh Claude Code session in this repo and confirm auto-injection (the hook script itself smoke-tested green).

## 🔷 Next up (ranked by leverage)

1. **T506a notebook audit** — Jupyter notebook using OpenAI `text-embedding-3-large` to rerank one prospect's CSV. Unblocks GTM (ADR 011's primary recommendation). ~1 hr. **Single highest-EV item in the project.**
2. **T101b — fetch + commit 6 DGT PDFs** — `.gitignore` already allows; just download + commit. ~10 min. Unblocks T102b/T103b.
3. **T113-verify — run `build-graph-db` against real graph** — confirms ADR 007 end-to-end. ~15 min.
4. **T102b/T103b — LLM re-extract ITI content** — kills the provenance risk (ADR 008) + rebalances toward 2W/3W. ~2–3 hr.
5. **ASDC/HSN/NHTSA parser audit** — is the ITI hand-curation pattern repeated elsewhere? ~30 min.
6. **T603a upgrade + T603-verify + T603e promote** — per-function `Random(42)`, verify determinism, move files into `golden/`. ~20 min.
7. **T102c public framing update** — PRODUCT.md + decisions/003 — disclose v1 hand-curation. ~15 min.
8. **Xfail `test_iti_scraper::test_minimum_100_chains`** — green CI; link to T103b. ~5 min.

## 🗝 Key recent decisions

- **Stay vertical (auto parts).** Market research: Algolia zero Hindi NLP; Klevu's #1 complaint is cost; Sajari→Algolia-acquired. Horizontal loses for a solo founder; Indian-language multilingual commerce is the real wedge (ADR 011).
- **Collapse Phase 3 + 4.** Unit of work = `(pair_strategy, model, benchmark)` triple, not a data file (ADR 006).
- **SQLite for KG.** JSON = committed inputs; `.db` = derived + gitignored (ADR 007).
- **ITI content is hand-curated v1.** Disclose publicly; LLM re-extract in Phase 2b (ADR 008).
- **Session-hygiene is now a global rule.** `~/.claude/rules/session-hygiene.md` means Claude auto-maintains this file + the canonical scaffold without user prompting.

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = measured outcome (see `memory/regressions.md`).
- Do NOT generate training pairs without a model to consume them. Open-loop Phase 3 burned a week.
- `TASKS.md` is the single task-board source. Never introduce a parallel tool-state board.
- CLAUDE.md stays under ~100 lines / 2,500 tokens. Architecture → skills; decisions → ADRs.

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds. You know where we are.
- **Claude starting a session:** auto-injected via the global `SessionStart` hook (`~/.claude/hooks/session-state.sh`). Also available via `/status`.
- **Claude ending a session:** run `/wrap`. Updates this file + offers commit.
- **If this is stale:** run `/status` to refresh from git log + TASKS.md, or `/wrap` to force a rewrite.
