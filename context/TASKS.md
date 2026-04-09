# Task Board

Last updated: 2026-04-09

## Labels
- **Phase**: P1 (dataset), P2 (knowledge graph), P3 (enhanced training), P4 (model), P5 (search system), P6 (product/GTM)
- **Type**: `eng` (engineering), `research` (investigation), `data` (data collection/processing), `product` (product decisions), `design` (UX/demo)
- **Size**: S (< 2 hrs), M (2-4 hrs), L (4-8 hrs), XL (multi-day)
- **Priority**: P0 (blocking), P1 (important), P2 (nice to have)

---

## ✅ Done

### Phase 1: Training Dataset Pipeline

| ID | Task | Type | Size | Notes |
|----|------|------|------|-------|
| T001 | Build project scaffolding (schemas, config, CLI) | eng | S | `auto_parts_search/` package |
| T002 | Build Shopify scraper (SparesHub, Bikespares, eAuto) | eng | M | 24,865 products scraped |
| T003 | Build Playwright scraper (Boodmo, Autozilla) | eng | M | 479 products + 1.4M sitemap URLs |
| T004 | Build vocabulary pair generator from research | eng | M | 1,593 pairs (synonym, misspelling, symptom, brand-generic) |
| T005 | Build catalog pair generator | eng | S | Groups by category+vehicle, generates pos/neg pairs |
| T006 | Build 195-query evaluation benchmark | eng | M | 6 query types, 3 difficulty levels |
| T007 | Build CLI orchestrator | eng | S | `python3 -m auto_parts_search [scrape\|pairs\|benchmark\|stats]` |
| T008 | Research: audit 98 Indian auto parts platforms | research | L | Reports in `../auto-parts-research/` |
| T009 | Research: vocabulary, misspellings, mechanic slang | research | L | 50+ Hindi/English pairs, symptom mappings |
| T010 | Research: competitive landscape | research | M | No direct competitor in India confirmed |
| T011 | Research: identify govt/educational data sources | research | M | HSN codes, DGT syllabi, NHTSA, ASDC, TecDoc |
| T012 | Create project management structure | eng | S | context/, memory/, decisions/, plans/ |

---

## 📋 Backlog

### Phase 2: Knowledge Graph

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T100 | Scrape HSN code taxonomy (Ch. 8708, 84, 85) | data | M | P0 | — | `data/knowledge_graph/hsn_taxonomy.json` with 200+ codes in parent-child hierarchy |
| T101 | Download 6 DGT ITI syllabus PDFs | data | S | P0 | — | All 6 PDFs saved locally |
| T102 | Parse ITI syllabi: extract part lists per system | eng | L | P0 | T101 | `iti_systems.json` mapping 8+ vehicle systems → their parts |
| T103 | Parse ITI syllabi: extract diagnostic chains | eng | M | P0 | T101 | `iti_diagnostics.json` with 100+ symptom → diagnosis → parts chains |
| T104 | Pull NHTSA vPIC API: vehicle taxonomy | data | M | P1 | — | `nhtsa_vehicles.json` with makes/models for Indian brands (Suzuki, Hyundai, Honda, Toyota, Tata) |
| T105 | Pull NHTSA API: recall data → part-vehicle mappings | data | M | P1 | T104 | `nhtsa_recalls.json` with component→vehicle cross-references |
| T106 | Download & parse ASDC qualification packs (top 10) | data | M | P1 | — | `asdc_tasks.json` with task→parts→knowledge mappings |
| T107 | Evaluate TecDoc RapidAPI free tier | research | S | P2 | — | Decision doc: is free tier useful? Sample cross-references pulled |
| T108 | Pull TecDoc cross-references (if free tier works) | data | M | P2 | T107 | `tecdoc_crossref.json` with OEM↔aftermarket part equivalences |
| T109 | Design knowledge graph schema | eng | S | P0 | — | JSON schema for nodes (Part, Category, System, Vehicle, Symptom, Alias) and edges |
| T110 | Build knowledge graph assembly script | eng | L | P0 | T100,T102,T103,T104,T109 | `graph.json` merging all sources, validation tests pass |
| T111 | Write knowledge graph validation tests | eng | M | P0 | T110 | Tests: connectivity, no orphans, all parts have ≥1 edge, edge type coverage |
| T112 | Map Boodmo 371K part names to HSN categories | eng | M | P1 | T100 | Each of the top 1000 Boodmo part names assigned an HSN category |

### Phase 3: Enhanced Training Data

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T200 | Generate hierarchy pairs from HSN taxonomy | eng | M | P0 | T100 | Graded similarity pairs: siblings=0.85, cousins=0.4, distant=0.2 |
| T201 | Generate system-membership pairs from ITI data | eng | M | P0 | T102 | "brake pad" ↔ "braking system" = 1.0 pairs |
| T202 | Generate diagnostic chain pairs from ITI data | eng | M | P0 | T103 | "grinding noise when braking" ↔ "brake pad" pairs with labels |
| T203 | Generate vehicle-part compatibility pairs from NHTSA | eng | M | P1 | T105 | "brake pad + Honda City 2019" = valid combination pairs |
| T204 | Generate cross-reference pairs from TecDoc | eng | S | P2 | T108 | OEM part# ↔ aftermarket part# equivalence pairs |
| T205 | Generate task-based pairs from ASDC data | eng | S | P1 | T106 | "brake inspection" ↔ ["pad", "disc", "fluid"] pairs |
| T206 | Merge all pair sources into unified training set | eng | M | P0 | T200-T205 | Single `all_pairs_v2.jsonl` with pair_type and source tags |
| T207 | Implement graded similarity labels | eng | M | P0 | T200 | Replace binary 1.0/0.0 with graph-distance-based scores |
| T208 | Update benchmark with knowledge-graph-aware expected results | eng | S | P1 | T110 | Benchmark queries reference graph nodes for precise evaluation |

### Phase 4: Embedding Model

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T300 | Evaluate base models (Jina v3, multilingual-MiniLM, BGE-m3) | research | M | P0 | — | Benchmark scores for each base model on our 195 queries |
| T301 | Set up fine-tuning pipeline (sentence-transformers) | eng | M | P0 | T206 | Script that loads pairs, trains model, saves checkpoint |
| T302 | Train v1 model on vocabulary pairs only | eng | M | P0 | T301 | Model checkpoint + benchmark score > base model by 10%+ |
| T303 | Train v2 model on full pair set (vocab + knowledge graph) | eng | L | P0 | T206,T302 | Model checkpoint + benchmark score > v1 by 10%+ |
| T304 | Experiment: multi-task loss (synonym vs hierarchy vs compat) | eng | L | P2 | T303 | Compare single-task vs multi-task performance |
| T305 | Benchmark vs OpenAI embeddings | eng | S | P0 | T303 | Side-by-side comparison on 195 queries, documented |
| T306 | Benchmark vs Cohere multilingual v3 | eng | S | P1 | T303 | Side-by-side comparison, Hindi/Hinglish subset focus |
| T307 | Model quantization for inference speed | eng | M | P1 | T303 | ONNX export, measure latency p50/p95 |
| T308 | Write model evaluation report | product | M | P0 | T305,T306 | Markdown report with scores, examples, failure analysis |

### Phase 5: Search System

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T400 | Set up Qdrant vector DB | eng | S | P0 | T303 | Docker container running, products indexed |
| T401 | Build FastAPI search endpoint | eng | M | P0 | T400 | `POST /search` returns ranked results from embeddings |
| T402 | Add keyword search layer (Typesense or Elasticsearch) | eng | M | P0 | T401 | Hybrid: embedding + keyword, RRF score combination |
| T403 | Build query preprocessor | eng | M | P1 | T401 | Language detection, spelling correction, vehicle extraction |
| T404 | Add fitment filtering from knowledge graph | eng | M | P1 | T110,T401 | If vehicle in query → filter results by compatibility |
| T405 | Build catalog ingestion endpoint | eng | M | P0 | T400 | `POST /catalog/ingest` — upload CSV/JSON, auto-embed |
| T406 | Add search analytics (zero-result tracking) | eng | M | P1 | T401 | `GET /analytics/zero-results` returns failed queries |
| T407 | Add re-ranking layer | eng | M | P2 | T402 | Cross-encoder or rule-based re-ranker on top-50 results |
| T408 | Load testing (target: p95 < 200ms) | eng | M | P1 | T402 | Load test report with latency percentiles |
| T409 | Deploy to Railway/Render | eng | M | P0 | T402 | Live URL, health check passing |

### Phase 6: Product & GTM

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T500 | Build demo UI (split-screen comparison) | design | L | P0 | T402 | Next.js app: "their search" vs "our search" side by side |
| T501 | Build search audit report generator | eng | L | P0 | T406 | Input: search logs CSV → Output: PDF with zero-results, revenue loss estimate |
| T502 | Build Shopify search app | eng | XL | P1 | T402 | Installable Shopify app that replaces store search |
| T503 | Create landing page | design | M | P0 | T500 | Product website with demo embed |
| T504 | Write API documentation | product | M | P0 | T402 | OpenAPI spec + integration guide |
| T505 | Identify 5 target customers for pilot | product | M | P0 | — | Company names, contact info, catalog size, current search |
| T506 | Run free search audit for 3 prospects | product | L | P0 | T501,T505 | 3 delivered audit reports with conversion impact estimates |
| T507 | Convert 1 audit into paid pilot | product | L | P0 | T506 | Signed pilot agreement, API key issued |
| T508 | Set up billing (Stripe/Razorpay) | eng | M | P1 | T409 | Usage-based billing on API calls |
| T509 | Define pricing tiers | product | S | P0 | — | Free/Growth/Enterprise pricing documented |

### Cross-cutting

| ID | Task | Type | Size | Priority | Depends on | Definition of Done |
|----|------|------|------|----------|------------|-------------------|
| T600 | Set up CI (GitHub Actions: tests on push) | eng | S | P1 | — | Tests run on every push, badge in README |
| T601 | Create README.md | product | S | P1 | — | What it is, quick start, architecture diagram |
| T602 | Set up GitHub repo + push | eng | S | P0 | — | Public or private repo, code pushed |
| T603 | Data backup strategy for scraped data | eng | S | P2 | — | Raw data backed up (cloud storage or git-lfs) |

---

## Task Count Summary

| Phase | Total | S | M | L | XL |
|-------|-------|---|---|---|---|
| P1 (done) | 12 | 3 | 6 | 3 | 0 |
| P2 Knowledge Graph | 13 | 3 | 7 | 3 | 0 |
| P3 Enhanced Training | 9 | 2 | 6 | 1 | 0 |
| P4 Embedding Model | 9 | 2 | 5 | 2 | 0 |
| P5 Search System | 10 | 1 | 7 | 1 | 1 |
| P6 Product & GTM | 10 | 1 | 4 | 4 | 1 |
| Cross-cutting | 4 | 3 | 0 | 0 | 1 |
| **Total** | **67** | **15** | **35** | **14** | **3** |

## Critical Path

The fastest route to a working demo:

```
T100 (HSN) ──┐
T101 (PDFs) ─┤
T102 (parse) ┼──► T110 (graph) ──► T206 (merge pairs) ──► T301 (train pipeline)
T104 (NHTSA) ┤                                              │
T109 (schema)┘                                              ▼
                                                      T303 (train v2)
                                                            │
                                                            ▼
T300 (eval base) ──────────────────────────────────► T305 (benchmark)
                                                            │
                                                            ▼
                                                      T400 (Qdrant)
                                                            │
                                                      T401 (FastAPI)
                                                            │
                                                      T402 (hybrid)
                                                            │
                                               ┌────────────┼────────────┐
                                               ▼            ▼            ▼
                                         T409 (deploy) T500 (demo) T501 (audit)
                                                            │
                                                      T505 (prospects)
                                                            │
                                                      T506 (free audits)
                                                            │
                                                      T507 (first customer)
```

## Sprint Suggestion

**Sprint 1 (Week 1)**: Phase 2A — Data Collection
- T100, T101, T104, T106, T107, T109

**Sprint 2 (Week 2)**: Phase 2B — Parse & Build Graph
- T102, T103, T105, T110, T111, T112

**Sprint 3 (Week 3)**: Phase 3 — Training Pairs
- T200, T201, T202, T203, T206, T207

**Sprint 4 (Week 4)**: Phase 4 — Model Training
- T300, T301, T302, T303, T305, T308

**Sprint 5 (Week 5-6)**: Phase 5 — Search System
- T400, T401, T402, T403, T405, T409

**Sprint 6 (Week 6-7)**: Phase 6 — Product
- T500, T501, T503, T504, T505

**Sprint 7 (Week 8)**: First Customer
- T506, T507, T509
