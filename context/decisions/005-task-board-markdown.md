# Decision 005: Task board lives in markdown, not Cline Kanban

**Date**: 2026-04-12
**Status**: Decided

## Context
Dual task boards have been running in parallel:
- `context/TASKS.md` (hand-written markdown)
- `context/cline-kanban-board.json` (Cline tool state)

They drifted. PROJECT_LOG.md:8845 records T200/T201/T202/T206 being trashed in the kanban on 2026-04-11; TASKS.md still listed them as Backlog on 2026-04-12 when an audit caught it. Dual sources of truth always drift.

## Decision
`context/TASKS.md` is the single source of truth. Delete `context/cline-kanban-board.json` from the repo.

## Why markdown wins
- Greppable, diffable in git, readable without tooling.
- Survives Cline (or any tool) going away.
- Forces explicit human reconciliation after each work session — prevents silent drift.
- PRs can show task state changes inline with code.

## How Cline still gets used (optional)
If the Cline UI is still useful for visualization, generate a kanban view *from* TASKS.md on demand (small parser). Cline's JSON becomes a derived artifact, never an authoritative one.

## Consequences
- After every work session, update TASKS.md manually (~30 sec).
- If a task moves to done, move it to the Done section with the commit hash as evidence.
- If a task is dropped, log it in `memory/regressions.md` with reason.
