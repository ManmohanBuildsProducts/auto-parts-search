# Decision 003: Knowledge Graph Before Embeddings

**Date**: 2026-04-09
**Status**: Decided

## Context
Original plan: scrape catalogs → generate pairs → fine-tune model. Discovery of government/educational data sources changes the approach.

## Decision
Build a knowledge graph BEFORE training the embedding model. The graph encodes domain relationships that the model learns to represent in vector space.

## Why This Matters
Without the graph, we get "better fuzzy search" — shocker ≈ shock absorber.
With the graph, we get "auto parts intelligence":
- Part hierarchy (brake pad and brake disc are siblings under Braking System)
- Diagnostic chains (grinding noise → worn brake pad → replace pad + inspect disc)
- Compatibility (this brake pad fits Swift 2019 but not Creta)
- Cross-references (Maruti OEM 16510M68K00 = Bosch F002H234FF)

## Graph Schema
```
Nodes: Part, Category, System, Vehicle, Symptom, Alias
Edges: is_a, in_system, caused_by, fits, equivalent_to, known_as
```

## Impact on Training
- Graded similarity (not just binary) based on graph distance
- Multi-type training pairs from different edge types
- Potentially multi-task loss functions per edge type

---

## 2026-04-12 provenance addendum (see ADR 008)

When this ADR was written, it implied DGT ITI syllabus content would be extracted from PDFs. The current `iti_systems.json` (124 parts) and `iti_diagnostics.json` (103 chains) are **~95% hand-curated Python dicts** derived from the founder's reading of the syllabi, not from programmatic extraction. The PDFs are in `data/knowledge_graph/iti_pdfs/` (gitignored until T101b).

ADR 008 documents this honestly and queues T102b/T103b for LLM-based re-extraction with per-entry `provenance: {method, pdf, page}` fields. Until T102b/T103b ship, external-facing materials (PRODUCT.md moat claim, sales pitches) must describe v1 as hand-curated, v2 as LLM-extracted.

Other KG sources (HSN, NHTSA, ASDC) were audited 2026-04-12 and appear clean — real network scraping, no hand-curation pattern. Only ITI has the provenance issue.
