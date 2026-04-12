# Phase 2b Plan: Cleanup — SQLite + ITI re-extraction + reproducibility

**Status**: Not started
**Depends on**: Phase 2 (done; commits e0fd9da and earlier)
**Blocks**: Phase 3 (training loop)
**Decisions**: ADR 007, 008, 009

## Objective
Close the audit gaps found on 2026-04-12 before starting Phase 3. Three independent tracks, all P0, can be worked in parallel.

---

## Track A — SQLite migration (ADR 007)

| ID | Task | Size | DoD |
|----|------|------|-----|
| T113a | Add SQLite schema + loader in `auto_parts_search/graph_db.py` | S | Module exposes `GraphDB` class with `insert_nodes`, `insert_edges`, `query_*` helpers, FTS search. |
| T113b | `scripts/build_graph_db.py` | S | Reads existing JSON KG inputs via `auto_parts_search.build_graph`, materializes to `data/knowledge_graph/graph.db`. Idempotent. |
| T113c | `tests/test_graph_db.py` | S | Invariants: every part has ≥1 edge, no orphan nodes, indexed lookup <1ms on 100K-row test. |
| T113d | CLI: `python3 -m auto_parts_search build-graph-db` | S | Command wired; `stats` command shows .db row counts. |
| T113e | Update search-path code (future) to query .db instead of JSON | M | Deferred until Phase 5 T404 (fitment filter). |

---

## Track B — ITI re-extraction (ADR 008)

| ID | Task | Size | DoD |
|----|------|------|-----|
| T101b | Commit DGT ITI PDFs to git | S | Remove `*.pdf` exclusion for `data/knowledge_graph/iti_pdfs/`. Commit 6 PDFs (~9MB). |
| T102b | LLM-extract systems+parts from each PDF | M | New `iti_systems_v2.json` with 200+ additional parts, each with `provenance: {method, pdf, page}`. Merged with hand-curated v1, dedup by name+system. |
| T103b | LLM-extract diagnostic chains from each PDF | M | New `iti_diagnostics_v2.json` with 150+ additional chains. Rebalance toward 2W/3W/tractor (current v1 is 64% LMV/HMV). |
| T102c | Update public framing | S | `memory/learnings.md`, `context/PRODUCT.md`, decisions/003 — disclose v1 was hand-curated; v2 is LLM-extracted. |

### Extraction approach (LLM with 1M context)
Prompt template per PDF:
```
Input: full text of <PDF>
Output schema: {
  systems: [{name, parts: [{name, aliases, role, source_page}]}],
  diagnostics: [{symptom, system, diagnosis_steps, related_parts, vehicle_type, source_page}]
}
Constraints: only include entries you can cite to a specific page; aliases must be Indian-English/Hindi if mentioned.
```
One call per PDF. Merge output into existing JSON, keeping hand-curated entries where LLM extraction is weaker.

---

## Track C — Reproducibility (ADR 009)

| ID | Task | Size | DoD |
|----|------|------|-----|
| T603a | Add `random.seed(42)` to `training/*.py` | S | `catalog_pairs.py`, `vocabulary_pairs.py`, `benchmark.py`. Verified deterministic via two consecutive runs. |
| T603b | Create `data/raw/MANIFEST.md` template + first manifest entry | S | Schema committed; first entry describes the current April-2026 scrape with SHA256s. |
| T603c | Upload first snapshot to Backblaze B2 | S | Tarball URL + SHA256 filled into MANIFEST.md. |
| T603d | `scripts/fetch_raw.py` | S | Reads MANIFEST, downloads latest, extracts, verifies SHA256. |
| T603e | Golden dir convention | S | `data/training/golden/README.md` + `METADATA.md` written. Current `*.jsonl` files moved into golden/ once tests pass. |

---

## Track D — Housekeeping (ADR 005)

| ID | Task | Size | DoD |
|----|------|------|-----|
| T604 | Delete `context/cline-kanban-board.json` | S | Removed from HEAD; TASKS.md is single source. |
| T605 | Reconcile TASKS.md with git reality | S | Phase 2 tasks moved to Done with commit hashes cited. This plan referenced. |

---

## Parallelization
Tracks A, B, C, D are fully independent. Can be worked by separate sessions/agents. Track B is the highest-value (moat-relevant); track C is the highest-risk-of-embarrassment (reproducibility). Track A unblocks Phase 5. Track D is paperwork.

## Out of scope
- No new data sources (TecDoc Pro, IndiaMART, etc.) — Phase 6.
- No pair generation — Phase 3.
- No search system — Phase 5.
