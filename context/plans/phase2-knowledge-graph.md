# Phase 2 Plan: Knowledge Graph

**Status**: Not started
**Depends on**: Phase 1 (done)
**Blocks**: Phase 3 (enhanced training data)

## Objective
Build a structured knowledge graph from government/educational sources that encodes auto parts domain knowledge: part taxonomy, system membership, diagnostic chains, vehicle compatibility, and cross-references.

## Tasks

### 2A: HSN Code Taxonomy (1-2 hours)
- [ ] Scrape HSN code hierarchy from ClearTax or Seair
- [ ] Focus: Chapter 8708 (vehicle parts), 84 (mechanical), 85 (electrical)
- [ ] Output: `data/knowledge_graph/hsn_taxonomy.json`
- [ ] Structure: `{code, description, parent_code, children[], level}`

### 2B: DGT ITI Syllabi Parsing (3-4 hours)
- [ ] Download 6 PDFs from dgt.gov.in
- [ ] Parse with PyPDF2 or pdfplumber
- [ ] Extract per module: system name, part lists, diagnostic procedures
- [ ] Build: system→parts mapping, symptom→diagnosis→parts chains
- [ ] Output: `data/knowledge_graph/iti_systems.json`, `data/knowledge_graph/iti_diagnostics.json`

### 2C: NHTSA API Pull (2-3 hours)
- [ ] Hit vPIC API for vehicle makes/models (Indian brands: Maruti/Suzuki, Hyundai, Honda, Toyota, Tata, Mahindra, Kia)
- [ ] Pull recall data for these makes → extract component→vehicle mappings
- [ ] Output: `data/knowledge_graph/nhtsa_vehicles.json`, `data/knowledge_graph/nhtsa_recalls.json`

### 2D: ASDC Qualification Packs (2 hours)
- [ ] Download top 10 automotive QPs from asdc.org.in
- [ ] Extract: task→parts→knowledge mappings per job role
- [ ] Output: `data/knowledge_graph/asdc_tasks.json`

### 2E: TecDoc Evaluation (1 hour)
- [ ] Check RapidAPI free tier limits for TecDoc catalog
- [ ] Pull sample cross-references for top 20 part types
- [ ] Evaluate: is the free tier enough for MVP?
- [ ] Output: `data/knowledge_graph/tecdoc_crossref.json` (if accessible)

### 2F: Graph Assembly (3-4 hours)
- [ ] Merge all sources into unified knowledge graph
- [ ] Node types: Part, Category, System, Vehicle, Symptom, Alias, Brand
- [ ] Edge types: is_a, in_system, caused_by, fits, equivalent_to, known_as
- [ ] Store as JSON + optional SQLite for querying
- [ ] Output: `data/knowledge_graph/graph.json`
- [ ] Write validation tests: graph connectivity, no orphan nodes, all parts have at least one edge

## Acceptance Criteria
- Graph has 1000+ part nodes (from HSN + ITI + Boodmo names)
- At least 5 edge types populated
- Every part has at least one `is_a` edge (category from HSN)
- At least 100 symptom→part diagnostic chains (from ITI syllabi)
- At least 50 vehicle→part compatibility edges (from NHTSA)
- Tests pass
