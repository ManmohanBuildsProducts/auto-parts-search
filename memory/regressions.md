# Regressions & Incidents

Things that went wrong, why, and how to avoid repeating them.

---

## 2026-04-11: Phase 3 pair-generation open-loop (T200/T201/T202/T206 trashed)

**What happened.** Between 2026-04-09 and 2026-04-11, Phase 3 tasks T200 (HSN hierarchy pairs), T201 (ITI system pairs), T202 (diagnostic chain pairs), and T206 (merge all to `all_pairs_v2.jsonl`) were executed end-to-end. Output files were generated (PROJECT_LOG:7841 shows `hsn_hierarchy_pairs.jsonl` at 1,300 lines + a parser + tests committed in that branch). All four tasks were then trashed in Cline Kanban on 2026-04-11.

**Why it failed.** Open-loop execution. No model was trained on the output to validate whether the chosen pair-generation strategy improved or hurt benchmark scores. The "done" criterion — "graded similarity pairs: siblings=0.85, cousins=0.4, distant=0.2" — was a schema claim, not an outcome claim. Without a model in the loop, the judgment "is this pair set good?" cannot be made.

**How to avoid.** ADR 006 collapses Phase 3 (pair gen) + Phase 4 (model) into a single training loop. The atomic unit is the triple `(pair_gen_strategy, model_checkpoint, benchmark_score)`. No pair-generation variant is declared done until a model has been trained on it and benchmarked. Experiments live under `data/training/experiments/<date>-<hypothesis>/`; only promoted results touch `data/training/golden/`.

**What to reuse.** The trashed code likely contains valid work (graph-distance calculation, graded-label scaffolding). Before starting T200b/T201b/T202b, check the reflog or the trashed kanban entries for salvageable code.

---

## 2026-04-09 (discovered 2026-04-12): TASKS.md / Cline Kanban drift

**What happened.** Two authoritative task boards running in parallel (`context/TASKS.md` and `context/cline-kanban-board.json`). Phase 2 tasks T100–T111 were completed (commits 4cae4c1, 0694bc1, 53e32e9, 34e5968, 7ce13be, 7f51fa9, 95063dc, 064e161, 3d1bb09) but TASKS.md still listed them under "Backlog" on 2026-04-12.

**Why it failed.** Dual sources of truth. Cline updates its JSON on task-state changes; TASKS.md required manual update and didn't get one. No reconciliation step.

**How to avoid.** ADR 005: TASKS.md is the single source. Cline's JSON is deleted. Manual update to TASKS.md is the mandatory post-session step.

---

## 2026-04-12: ITI provenance overclaim (discovered audit, not incident yet)

**What happened.** Commit message "Add ITI syllabus parser for diagnostic chains (Phase 2, T103)" and decisions/003 ("DGT ITI syllabi are the richest single source") imply that the 103 diagnostic chains and 124 parts in `iti_*.json` were extracted from PDFs. Audit on 2026-04-12 found they are ~95% hand-curated in Python (`scrapers/iti_scraper.py:280–1635` is `STRUCTURED_DIAGNOSTICS` as a hardcoded dict; `scrapers/iti_systems_parser.py:35–277` is `VEHICLE_SYSTEMS` as a hardcoded list). PDFs are `*.pdf`-gitignored and never committed, so the parser runs on zero PDFs on a fresh clone and produces the same output — proving 100% hand-curation.

**Why it matters.** Not yet an incident. Becomes one the first time a prospect/investor asks "show me how you extracted this from DGT syllabi." The answer "I hand-curated it based on my reading" is fine and honest; "extracted by the parser" as commits imply is not defensible.

**How to avoid.** ADR 008 (disclosure + re-extraction plan). T101b commits the PDFs; T102b/T103b re-extract via LLM with per-entry provenance. Public framing updated: v1 is hand-curated; v2 is LLM-extracted.

---

## Pattern to watch: claiming "done" without outcome evidence

All three incidents above share a structure: the builder moved work to "done" based on an artifact existing (a pair file, a kanban card, a JSON file) rather than an outcome being measured (a benchmark score, a reconciled git state, a traceable provenance). Principle going forward:

> **Done is not an artifact. Done is a verified outcome.**

If you can't point to a number, a commit hash, or a provenance trail, it's not done — it's a work-in-progress that someone forgot to finish.
