# CLAUDE.md

Project: Indian auto parts domain-specific embedding model + search API. Hindi/Hinglish, misspellings, symptoms, part-number cross-refs. Solo founder, part-time.

## Start every session here (canonical load order)

1. **`SESSION_STATE.md`** — rolling 1-page dashboard. Auto-injected via `SessionStart` hook (`.claude/settings.local.json`). Also available via `/status`.
2. **`context/INDEX.md`** — map of all docs (ADRs, plans, research, session logs).
3. **`context/TASKS.md`** — single source of truth for the task board.
4. **`memory/regressions.md`** — incidents to avoid repeating.
5. Any ADR in `context/decisions/` relevant to the current task.
6. The `architecture` skill — loads on demand when editing scrapers, KG, training, or the graph DB.

Use `/start` to run this load automatically and get a 3-part briefing. Use `/wrap` at session end to update `SESSION_STATE.md` and commit.

## Project structure (brief)

```
context/         Product docs, ADRs, plans, research, session logs (see INDEX.md)
memory/          Durable learnings + regressions log (always-loaded at session start)
auto_parts_search/   Core Python package (config, schemas, build_graph, graph_db, __main__)
scrapers/        Platform + government data collectors
training/        Vocabulary + catalog pair generators + benchmark
tests/           pytest suite
scripts/         Build/ops scripts (build_graph_db, fetch_raw, etc.)
data/            raw/ (gitignored), training/golden/ (blessed), training/experiments/ (gitignored), knowledge_graph/*.json (inputs) + graph.db (derived)
.claude/         skills/ + commands/ + settings.local.json (see `architecture` skill for pipeline details)
```

Research data lives in sibling `../auto-parts-research/` (6 reports, 98 platforms audited).

## Commands

```bash
# Tests
python3 -m pytest tests/ -v
python3 -m pytest tests/test_graph_db.py -v

# CLI pipeline
python3 -m auto_parts_search scrape           # Run Shopify + Playwright scrapers
python3 -m auto_parts_search pairs            # Generate training pairs
python3 -m auto_parts_search benchmark        # Generate 195-query benchmark
python3 -m auto_parts_search graph            # Build graph.json from JSON inputs
python3 -m auto_parts_search build-graph-db   # Materialize SQLite graph.db (ADR 007)
python3 -m auto_parts_search stats            # Show data file counts
python3 -m auto_parts_search all              # Run scrape → pairs → benchmark → stats
```

Playwright scrapers require `python3 -m playwright install chromium`.

## Conventions Claude should honor (not derivable from code)

- **TASKS.md is the single task-board source** (ADR 005). Never introduce a parallel tool-state board.
- **"Done" = verified outcome, not artifact existence** (see `memory/regressions.md`).
- **No open-loop pair generation** — always train + benchmark a model on any new pair set (ADR 006).
- **Training pairs are deterministic** — every generator uses `random.seed(RANDOM_SEED)` from config (ADR 009).
- **Golden training set is immutable** — experiments branch into `data/training/experiments/<date>-<hypothesis>/`; promotion to `golden/` is a deliberate commit.
- **ITI knowledge graph v1 is hand-curated** (ADR 008) — disclose honestly in any external material.
- **Architecture details live in the `architecture` skill**, not this file. Invoke it when touching the pipeline.

## What to read vs what to skip

- **Read**: SESSION_STATE, INDEX, TASKS, regressions, learnings, relevant ADRs, relevant skill.
- **Skip**: `context/PROJECT_LOG.md` (17K lines — grep it narrowly, don't read whole).
- **Use subagent for**: codebase investigations spanning >5 files, market research, competitive analysis.

## When correcting Claude

If Claude violates a rule repeatedly, the file is probably too long — prune before adding new rules. This file targets <100 lines / <2,500 tokens (see ADR 011 + workflow research).
