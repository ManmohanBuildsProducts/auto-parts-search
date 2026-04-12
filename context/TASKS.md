# Task Board

Last updated: 2026-04-12
Single source of truth. `context/cline-kanban-board.json` is deprecated (ADR 005) — do not edit.

## Labels
- **Phase**: P1 (dataset), P2 (knowledge graph), P2b (cleanup), P3 (training loop), P5 (search system), P6 (product/GTM)
- **Type**: `eng`, `research`, `data`, `product`, `design`
- **Size**: S (<2h), M (2–4h), L (4–8h), XL (multi-day)
- **Priority**: P0 (blocking), P1 (important), P2 (nice to have)

---

## ✅ Done

### Phase 1: Training Dataset Pipeline (commits 5dbb526 + ee55a4a)

| ID | Task | Notes |
|----|------|-------|
| T001 | Project scaffolding | `auto_parts_search/` package |
| T002 | Shopify scraper | 24,865 products (SparesHub, Bikespares, eAuto) |
| T003 | Playwright scraper | 479 products + 1.4M Boodmo sitemap URLs |
| T004 | Vocabulary pair generator | 1,593 pairs |
| T005 | Catalog pair generator | 17,372 pairs |
| T006 | 195-query benchmark | 6 query types, 3 difficulty levels |
| T007 | CLI orchestrator | `python3 -m auto_parts_search [scrape\|pairs\|benchmark\|stats]` |
| T008–T011 | Research (98 platforms, vocabulary, competition, data sources) | In `../auto-parts-research/` |
| T012 | Project management structure | context/, memory/, decisions/, plans/ |

### Phase 2: Knowledge Graph

| ID | Task | Commit | Output |
|----|------|--------|--------|
| T100 | HSN taxonomy scrape | 4cae4c1, 3a562ff | `hsn_taxonomy.json` — 1,918 codes |
| T101 | Download 6 DGT ITI PDFs | 0694bc1 | `iti_pdfs/manifest.json` (PDFs gitignored — see T101b) |
| T102 | Parse ITI systems | 89dd111 | `iti_systems.json` — 13 systems, 124 parts **⚠ hand-curated, see ADR 008** |
| T103 | Parse ITI diagnostics | 53e32e9 | `iti_diagnostics.json` — 103 chains **⚠ hand-curated, see ADR 008** |
| T104 | NHTSA vPIC scraper | 34e5968 | `nhtsa_vehicles.json` |
| T105 | NHTSA recalls | 7ce13be | `nhtsa_recalls.json` |
| T106 | ASDC qualification packs | 7f51fa9 | `asdc_tasks.json` |
| T107 | TecDoc evaluation | e9091c7 | Decision: free tier for validation only (ADR 004) |
| T109 | Knowledge graph schema | 95063dc | `schema.json` + `schema_example.json` |
| T110 | Graph assembly script | 064e161 | 2,627 nodes, 7 edge types |
| T111 | Graph validation tests | 3d1bb09 | `tests/test_knowledge_graph.py` |

---

## 🗑 Dropped

| ID | Task | Reason |
|----|------|--------|
| T108 | Pull TecDoc cross-references | ADR 004: free tier too limited; Indian OEM coverage gap. Not worth it. |
| T200, T201, T202, T206 | Phase 3 open-loop pair generation | Trashed 2026-04-11 — no model in the loop to evaluate pair quality. See `memory/regressions.md` and ADR 006. Will be redone as T200b/T201b/T202b/T206b under Phase 3 training loop. |

---

## 📋 Backlog

### Phase 2b: Cleanup (plan: `context/plans/phase2b-cleanup.md`)

All P0. Four independent tracks.

**Track A — SQLite migration** (ADR 007)
| ID | Task | Size |
|----|------|------|
| T113a | `auto_parts_search/graph_db.py` — schema + queries | S |
| T113b | `scripts/build_graph_db.py` — build .db from JSON | S |
| T113c | `tests/test_graph_db.py` | S |
| T113d | CLI: `python3 -m auto_parts_search build-graph-db` | S |

**Track B — ITI re-extraction** (ADR 008)
| ID | Task | Size |
|----|------|------|
| T101b | Commit 6 DGT PDFs, update .gitignore | S |
| T102b | LLM-extract systems+parts from each PDF (with provenance) | M |
| T103b | LLM-extract diagnostic chains from each PDF | M |
| T102c | Public framing update — disclose v1 hand-curation | S |

**Track C — Reproducibility** (ADR 009)
| ID | Task | Size |
|----|------|------|
| T603a | `random.seed(42)` in `training/*.py` | S |
| T603b | `data/raw/MANIFEST.md` + first entry | S |
| T603c | Snapshot to Backblaze B2 | S |
| T603d | `scripts/fetch_raw.py` | S |
| T603e | Golden dir convention (move `*.jsonl` to `data/training/golden/`) | S |

**Track D — Housekeeping**
| ID | Task | Size |
|----|------|------|
| T604 | Delete `cline-kanban-board.json` | S |
| T605 | Reconcile TASKS.md with git reality | S (this file) |
| T112 | Boodmo → HSN category mapping (top 1K part names) | M |

### Phase 3: Training loop (plan: `context/plans/phase3-training-loop.md`)

Replaces old Phase 3 + Phase 4 (ADR 006). Unit of work = `(pair_gen_strategy, model_checkpoint, benchmark_score)` triple.

| ID | Task | Size | Priority |
|----|------|------|----------|
| T303a | `training/evaluate.py` harness | S | P0 |
| T208 | Split benchmark into dev/test | S | P0 |
| T208b | Expand ground-truth to top-20 graded | M | P0 |
| T303b | Base-model shootout (BGE-m3, Jina v3, e5, OpenAI, Cohere, Sarvam) | S | P0 |
| T303c | Pair schema decision (graded vs binary) | M | P0 |
| T303d | Loss function decision | M | P0 |
| T200b | HSN hierarchy graded pairs | M | P0 |
| T201b | ITI system-membership pairs | M | P0 |
| T202b | ITI diagnostic chain pairs | M | P0 |
| T205b | ASDC task-parts pairs | S | P1 |
| T203 | NHTSA compatibility pairs | M | P1 |
| T206b | Merge to `golden/all_pairs_v2.jsonl` | S | P0 |
| T302 | Train v1 (vocab+catalog) | M | P0 |
| T303e | Train v2 (full set) — stop if <10% over base | L | P0 |
| T305 | External benchmark (OpenAI, Cohere) | S | P0 |
| T307 | ONNX quantization | M | P1 |

### Phase 5: Search system

| ID | Task | Size | Priority |
|----|------|------|----------|
| T402a | Tokenizer pipeline (IndicNLP + IndicTrans2 + lemma map) — see ADR 010 | M | P0 |
| T402b | Meilisearch index + BM25 baseline | M | P0 |
| T402c | Hybrid fusion + query classifier | M | P0 |
| T402d | Domain lemma map (~300 entries) | S | P0 |
| T400 | Qdrant vector DB setup | S | P0 |
| T401 | FastAPI `/search` endpoint | M | P0 |
| T403 | Query preprocessor (lang detect, spelling, vehicle extract) | M | P1 |
| T404 | Fitment filter (soft boost, not hard filter) | M | P1 |
| T405 | `/catalog/ingest` endpoint | M | P0 |
| T406 | Zero-result analytics | M | P1 |
| T407 | Reranker layer (Cohere Rerank or cross-encoder) | M | P2 |
| T408 | Load testing (target p95 <200ms) | M | P1 |
| T409 | Deploy to Railway/Render | M | P0 |

### Phase 6: Product + GTM

**GTM tasks unblocked from technical dependencies (ADR 011).**

| ID | Task | Size | Priority |
|----|------|------|----------|
| T505 | Identify 5 target mid-market Indian auto-parts prospects | M | P0 |
| T506a | Notebook-based search audit (no API needed — `text-embedding-3-large` + prospect CSV + their queries) | S | P0 |
| T506 | Deliver 3 free audits to prospects | L | P0 |
| T507 | Convert 1 audit to paid pilot | L | P0 |
| T500 | Demo UI (split-screen comparison) | L | P1 |
| T501 | Search audit report generator | L | P1 |
| T502 | Shopify app | XL | P2 |
| T503 | Landing page | M | P1 |
| T504 | API documentation | M | P1 |
| T508 | Billing (Razorpay/Stripe) | M | P2 |
| T509 | Pricing tiers | S | P1 |

### Cross-cutting

| ID | Task | Size | Priority |
|----|------|------|----------|
| T600 | GitHub Actions CI | S | P1 |
| T601 | README.md | S | P1 |
| T602 | Push to GitHub | S | P0 |

---

## Critical path

**Phase 2b (parallel tracks) → Phase 3 training loop → Phase 5 search API → Phase 6 GTM**

GTM audit (T505/T506a) is **parallel** to Phase 2b+3 and should begin this sprint (ADR 011).

```
Phase 2b Track A (SQLite) ─┐
Phase 2b Track B (ITI)    ─┤
Phase 2b Track C (repro)  ─┼──► Phase 3 (training loop) ──► Phase 5 (search API) ──► Phase 6 paid pilot
Phase 2b Track D (clean)  ─┘
                                         │
T505 + T506a (notebook audit) ───────────┴─► T506 (free audits) ──► T507 (first paid customer)
```
