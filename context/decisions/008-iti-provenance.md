# Decision 008: ITI knowledge graph provenance disclosure + re-extraction plan

**Date**: 2026-04-12
**Status**: Decided (honesty disclosure + re-extraction roadmap)

## Context (audit finding, 2026-04-12)
The current `data/knowledge_graph/iti_systems.json` (13 systems, 124 parts) and `iti_diagnostics.json` (103 chains) are **~95% hand-curated in Python**, not extracted from DGT ITI PDFs.

Evidence (code inspection 2026-04-12):
- `scrapers/iti_systems_parser.py:35–277` — `VEHICLE_SYSTEMS` is a hardcoded Python list of 13 systems with 124 parts.
- `scrapers/iti_scraper.py:280–1635` — `STRUCTURED_DIAGNOSTICS` is a hardcoded dict of ~100 diagnostic chains including `source_trade`, `source_page`, `vehicle_type` fields.
- PDFs are used only for thin enrichment: `_scan_pdfs_for_parts` matches 12 regex patterns; `_validate_systems_against_pdfs` counts keyword hits; `_extract_chains_from_text` may add chains when PDFs are present.
- `.gitignore` line 10: `*.pdf`. The 6 DGT PDFs were never committed. On a fresh clone, the parser runs on zero PDFs and produces the exact same output — proving 100% of the committed content is hardcoded.

## Why this matters
The prior commit message "Add ITI syllabus parser for diagnostic chains (Phase 2, T103)" and decisions/003 ("DGT ITI syllabi are the richest single source") are **technically true but misleading**. The hand-curated content is decent quality on inspection, but claiming "extracted from DGT syllabi" to a prospect, investor, or collaborator is a truth-in-labeling problem.

## Secondary finding: 4W bias in hand-curation
Chains by vehicle type: LMV/HMV 66, 2W 12, tractor 12, EV 11, 3W 1, stationary 1. The founder's 4W familiarity biased the curation. memory/learnings.md:13 says 2W is the volume play (260M vehicles). Real ITI PDF extraction (Mechanic Two & Three Wheeler, 1.6MB ~150pp) would rebalance this.

## Decision
1. **Disclose the current state honestly in all external materials.** When pitching the KG, say: "v1 is hand-curated based on the founder's reading of DGT ITI syllabi; v2 will be LLM-extracted from PDFs." Do not claim machine extraction until it's true.
2. **Commit the 6 DGT PDFs to git** — remove the `*.pdf` exclusion for `data/knowledge_graph/iti_pdfs/`. Total ~9MB, one-time, reproducible source of truth.
3. **Execute re-extraction (phase2b)** — use Claude with 1M context to parse each PDF against a structured JSON schema and extract parts, systems, diagnostic chains, aliases with page citations. Merge novel entries into the existing hand-curated set.

## Re-extraction plan (see `context/plans/phase2b-cleanup.md`)
- T101b (S): Commit PDFs, update .gitignore.
- T102b (M): LLM-extract parts per system from each PDF, merge into `iti_systems.json`.
- T103b (M): LLM-extract diagnostic chains from each PDF, merge into `iti_diagnostics.json`.
- Each new/updated entry carries a `provenance: {method: "llm_extracted" | "hand_curated", source_pdf, source_page}` field.

## Expected yield
Rough estimate: 200+ additional parts, 150+ additional diagnostic chains, with better 2W and diesel coverage. Provenance becomes auditable.
