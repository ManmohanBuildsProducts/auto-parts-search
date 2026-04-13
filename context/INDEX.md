# Context Index

Master navigation for everything under `context/`, `memory/`, and related project knowledge.

**When in doubt:** start here, read the section headings, drill down. Or open `SESSION_STATE.md` at the repo root for the 1-page "where are we now" dashboard.

---

## Dashboard + skills (at project root / `.claude/`)

| File | Purpose |
|------|---------|
| [../SESSION_STATE.md](../SESSION_STATE.md) | **Rolling 1-page dashboard.** Always current. Updated by `/wrap`. Auto-injected by the global `SessionStart` hook. |
| [../CLAUDE.md](../CLAUDE.md) | Short pointer file. Canonical load order + conventions. <100 lines. |
| [../.claude/skills/architecture/SKILL.md](../.claude/skills/architecture/SKILL.md) | On-demand architectural knowledge — modules, data flow, design decisions, known gotchas. Loaded when editing scrapers / KG / training / graph DB. |

Global (not per-project, but governs this project's behavior): `~/.claude/commands/{start,status,wrap}.md` slash commands; `~/.claude/hooks/session-state.sh` hook; `~/.claude/rules/session-hygiene.md` convention.

---

## Product & direction

| File | Purpose |
|------|---------|
| [PRODUCT.md](PRODUCT.md) | Vision, problem, ICP, pricing, GTM playbook |
| [ROADMAP.md](ROADMAP.md) | Six phases with current status per phase |
| [TASKS.md](TASKS.md) | **Single source of truth** for task board. Updated every session. |

---

## Decision records (ADRs)

Architectural + strategic decisions. Numbered; never edited after status = "Decided" — supersede via new ADR.

| # | File | Subject |
|---|------|---------|
| 001 | [001-tech-stack.md](decisions/001-tech-stack.md) | Python + sentence-transformers stack |
| 002 | [002-data-sources.md](decisions/002-data-sources.md) | Catalog scraping + government sources + vocabulary research |
| 003 | [003-knowledge-graph-approach.md](decisions/003-knowledge-graph-approach.md) | KG before embeddings (see ADR 008 for provenance disclosure) |
| 004 | [004-tecdoc-evaluation.md](decisions/004-tecdoc-evaluation.md) | TecDoc RapidAPI free tier evaluation |
| 005 | [005-task-board-markdown.md](decisions/005-task-board-markdown.md) | TASKS.md single source; Cline Kanban deprecated |
| 006 | [006-phase3-training-loop.md](decisions/006-phase3-training-loop.md) | Phase 3+4 collapsed; T303 split; T206 post-mortem |
| 007 | [007-kg-sqlite-storage.md](decisions/007-kg-sqlite-storage.md) | SQLite for indexed KG queries |
| 008 | [008-iti-provenance.md](decisions/008-iti-provenance.md) | ITI v1 is hand-curated disclosure + v2 LLM re-extraction plan |
| 009 | [009-reproducibility.md](decisions/009-reproducibility.md) | Manifest + seed + golden-run convention |
| 010 | [010-search-tokenizer.md](decisions/010-search-tokenizer.md) | IndicNLP + IndicTrans2 + lemma map pipeline |
| 011 | [011-positioning-moat.md](decisions/011-positioning-moat.md) | Stay vertical; ONDC optionality; GTM unblocked |
| 012 | [012-phase3-compute-infra.md](decisions/012-phase3-compute-infra.md) | Phase 3 runs on Colab Free + HF Hub; $0 v1 budget |

---

## Implementation plans

Per-phase execution playbooks. Updated as scope evolves.

| File | Covers |
|------|--------|
| [plans/phase2-knowledge-graph.md](plans/phase2-knowledge-graph.md) | Original Phase 2 (mostly complete; see TASKS.md for status) |
| [plans/phase2b-cleanup.md](plans/phase2b-cleanup.md) | SQLite migration + ITI re-extraction + reproducibility (4 parallel tracks) |
| [plans/phase3-training-loop.md](plans/phase3-training-loop.md) | Unified training loop (replaces old Phase 3 + Phase 4) |

---

## Research

Market intelligence + vendor research. Dated; treat older reports as snapshots.

| File | Date | Topic |
|------|------|-------|
| [research/market-audit-2026-04-12.md](research/market-audit-2026-04-12.md) | 2026-04-12 | Horizontal commerce search vendor landscape (Constructor, Klevu/Athos, Vectara, Algolia Hindi gap, ONDC) |
| [research/claude-code-workflows-2026-04-12.md](research/claude-code-workflows-2026-04-12.md) | 2026-04-12 | Best practices for long-running Claude Code projects |
| [research/t505-prospects-2026-04-12.md](research/t505-prospects-2026-04-12.md) | 2026-04-12 | 5 mid-market Indian auto-parts pilot prospects (Pikpart, AutoDukan, Parts Big Boss top 3) |

## Scraping & prospect registry

Evergreen (updated per session, not dated):

| File | Purpose |
|------|---------|
| [scraping-queue.md](scraping-queue.md) | Running registry of auto-parts domains. Scrape status + outreach status + priority + notes. Both pilot prospects and scraping targets live here — they overlap. |

---

## Session logs

Per-session retrospectives. Use these to onboard a new session or human collaborator into current context.

| Directory | Session focus |
|-----------|---------------|
| [sessions/2026-04-12/](sessions/2026-04-12/) | Audit + cleanup + strategic review (7 ADRs, SQLite migration, ITI finding, market research, positioning) |

Each session directory contains three canonical files:
- `learnings.md` — domain and process insights
- `missed-vs-corrections.md` — what I got wrong and fixed, what was missed
- `tasks-vs-direction.md` — approved vs shipped ledger + next-step ranking

---

## Memory

Durable learnings and regression log, surfaced to every session start.

| File | Purpose |
|------|---------|
| [../memory/learnings.md](../memory/learnings.md) | Things not obvious from code (market facts, tech gotchas, vocabulary notes) |
| [../memory/regressions.md](../memory/regressions.md) | Incidents + their post-mortems + patterns to avoid |

---

## Code roadmap (for navigation, not ownership)

| Area | Location |
|------|----------|
| Core package | `auto_parts_search/` (config, schemas, build_graph, graph_db, __main__) |
| Scrapers | `scrapers/` (Shopify, Playwright/Boodmo, HSN, ITI, NHTSA, ASDC) |
| Training pair generators | `training/` (vocabulary_pairs, catalog_pairs, benchmark) |
| Build/ops scripts | `scripts/` (build_graph_db, fetch_raw — planned) |
| Tests | `tests/` (pytest; one file per major component) |
| Data inputs | `data/knowledge_graph/*.json` (committed), `data/knowledge_graph/iti_pdfs/*.pdf` (to be committed per T101b) |
| Data outputs | `data/training/*.jsonl` (current); `data/training/golden/` (blessed ref); `data/training/experiments/` (gitignored) |

---

## How to use this index

- **New session starting?** The global `SessionStart` hook auto-loads `SESSION_STATE.md` + recent commits + regressions. Then read `TASKS.md` + latest session retrospective if depth is needed.
- **Mid-session check-in?** Run `/status`.
- **Making a decision?** Check if an ADR already covers it. If yes, read + cite. If no, draft a new ADR before coding.
- **Planning a phase?** Write it in `plans/phaseN-<name>.md`. Reference it from `TASKS.md`.
- **Finishing a session?** Run `/wrap`. It updates `SESSION_STATE.md`, creates `sessions/<date>-<slug>/{learnings,missed-vs-corrections,tasks-vs-direction}.md` when warranted, and proposes commits.
- **Changing direction?** Supersede an ADR with a new higher-numbered ADR that links back. Never silently edit a Decided ADR.
