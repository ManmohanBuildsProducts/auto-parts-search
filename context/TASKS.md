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
| ID | Task | Size | Status |
|----|------|------|--------|
| T113a | `auto_parts_search/graph_db.py` — schema + queries | S | ✅ c958134 |
| T113b | `scripts/build_graph_db.py` — build .db from JSON | S | ✅ c958134 |
| T113c | `tests/test_graph_db.py` | S | ✅ c958134 |
| T113d | CLI: `python3 -m auto_parts_search build-graph-db` | S | ✅ c958134 |
| T113-verify | Run end-to-end against real 2,627-node graph | S | ✅ 775e446 (3.3MB graph.db) |

**Track B — ITI re-extraction** (ADR 008)
| ID | Task | Size | Status |
|----|------|------|--------|
| T101b | Commit 6 DGT PDFs, update .gitignore | S | ✅ 775e446 (~8.7MB) |
| T102b | LLM-extract systems+parts from each PDF (with provenance) | M | ✅ a4eb69d (20 systems / 608 parts) |
| T103b | LLM-extract diagnostic chains from each PDF | M | ✅ a4eb69d (154 chains / 168 aliases) |
| T102c | Public framing update — disclose v1 hand-curation | S | ✅ 775e446 (decisions/003 + PRODUCT.md) |
| T113-audit | Audit ASDC/HSN/NHTSA for same hand-curation pattern | S | ✅ 775e446 (clean; only ITI affected) |
| T110b | Integrate v2 into `build_graph.py`; rebuild graph.db | M | ✅ a99f83c (4,252 nodes / 5,445 edges; +62% vs v1) |

**Track C — Reproducibility** (ADR 009)
| ID | Task | Size | Status |
|----|------|------|--------|
| T603a | Per-function `Random(seed)` in `training/*.py` | S | ✅ 775e446 |
| T603a-verify | Two consecutive runs byte-identical | S | ✅ 775e446 |
| T603b | `data/raw/MANIFEST.md` + first entry | S | 🟡 c958134 (template with TBD SHA256) |
| T603c | Snapshot to Backblaze B2 | S | Blocked (B2 credentials) |
| T603d | `scripts/fetch_raw.py` | S | Backlog |
| T603e | Promote `*.jsonl` + benchmark to `data/training/golden/` | S | ✅ 775e446 (golden-v1) |

**Track D — Housekeeping**
| ID | Task | Size | Status |
|----|------|------|--------|
| T604 | Delete `cline-kanban-board.json` | S | ✅ 3f2b187 |
| T605 | Reconcile TASKS.md with git reality | S | ✅ c92c94b |
| T112 | Boodmo → HSN category mapping (top 1K part names) | M | Backlog |

**Track E — Session dashboard (shipped this session 2026-04-12)**
| ID | Task | Size | Status |
|----|------|------|--------|
| T700 | `SESSION_STATE.md` dashboard at repo root | S | ✅ 35ce0e9 |
| T701 | `/start` `/status` `/wrap` slash commands (global at `~/.claude/commands/`) | S | ✅ ae19f95 |
| T702 | Global SessionStart hook (`~/.claude/hooks/session-state.sh`) — smoke-tested | S | ✅ (global install) |
| T703 | `~/.claude/rules/session-hygiene.md` + global CLAUDE.md reference | S | ✅ (global install) |
| T704 | `architecture` skill at `.claude/skills/architecture/SKILL.md` | S | ✅ 35ce0e9 |
| T705 | Trim CLAUDE.md to <100 lines; point at `SESSION_STATE.md` + `INDEX.md` | S | ✅ 35ce0e9 |
| T706 | Live-verify hook fires in a fresh session | S | Blocked (user action) |

### Phase 3: Training loop (plan: `context/plans/phase3-training-loop.md`)

Replaces old Phase 3 + Phase 4 (ADR 006). Unit of work = `(pair_gen_strategy, model_checkpoint, benchmark_score)` triple.

| ID | Task | Size | Priority |
|----|------|------|----------|
| T303a | `training/evaluate.py` harness | S | ✅ Done 2026-04-13 (63cf909) |
| T208 | Split benchmark into dev/test | S | ✅ Done 2026-04-13 (599fbf1) — 149 dev / 46 sealed test |
| T208b | Expand ground-truth to top-20 graded | M | ✅ Done 2026-04-13 (6166a85 + d4db804) — DeepSeek V3 judge, 149×20 labels |
| T303b | Base-model shootout (BGE-m3, e5-large, MiniLM) | S | ✅ Stage A done 2026-04-13 (3282d67) — Jina v3 skipped (broken install); OpenAI/Cohere deferred to T305 |
| T303c | Pair schema decision (graded vs binary) | M | P0 — unblocked by T208b |
| T303d | Loss function decision | M | P0 |
| T200b | HSN hierarchy graded pairs | M | ✅ Done 2026-04-13 (807c529) — 1,753 pairs, sibling 0.85 / cousin 0.40 |
| T201b | ITI system-membership pairs | M | ✅ Done 2026-04-13 (c284532; label-fix 95000f1) — 2,902 pairs |
| T202b | ITI diagnostic chain pairs | M | ✅ Done 2026-04-13 (c284532; label-fix 95000f1) — 4,556 pairs |
| T205b | ASDC task-parts pairs | S | P1 |
| T203 | NHTSA compatibility pairs | M | P1 |
| T206b | Merge to `golden/all_pairs_v2.jsonl` | S | ✅ Done 2026-04-13 (b3cca6e) — 26,760 pairs, SHA 7157b634… |
| T302 | Train v1 (vocab+catalog) | M | ✅ Done 2026-04-13 (8538881 + 00f6044 + 2d9bc06) — v1.2 auto-parts-search-v1 on HF |
| T303e | Train v3 (disciplined v1.2 recipe; 2-epoch + checkpointing) | L | ✅ Done 2026-04-13 (b2f368f) — v3 +4.4% graded nDCG@10 over v1.2; promoted per ADR 014 |
| T305 | External benchmark (OpenAI, Cohere) | S | Deferred — per ADR 015 Phase 3 closed before getting here; revisit during Phase 5 if still relevant for sales |
| T307 | ONNX quantization | M | Deferred to Phase 5 (production serving path) |
| T4-ablation | v4 A/B/C ablation (YT / Aksharantar / Hinglish bridge) | L | ✅ Done 2026-04-14 — all three failed +10% gate; ADR 015 |
| T5 | v5 — queryified YT + Aksharantar | L | ✅ Done 2026-04-14 — failed +5% gate (−1.6% overall, +14% symptom, −21% misspelled); ADR 015 |
| T-phase3-close | Ship v3, ADR 015, pivot to Phase 5 | S | ✅ Done 2026-04-14 |

### Phase 5: Search system

| ID | Task | Size | Priority |
|----|------|------|----------|
| T402a | Tokenizer pipeline (IndicNLP + Sarvam fallback) — see ADR 010 | M | ✅ Done 2026-04-14 (`6227d4b` + `dac7dda`) — 26 tests green, 81% cross-script expansion via bridge |
| T402b | Meilisearch index + BM25 baseline | M | ✅ Done 2026-04-14 (`c5e2c4b`) — 884 KG docs; MRR 0.297; typo+dual-script verified |
| T402c | Hybrid fusion + query classifier | M | ✅ Done 2026-04-14 (`34fad4b`, **ADR 016**) — +46% part_number; class-weighted RRF |
| T402d | Domain lemma map (~300 entries) | S | ✅ Absorbed into T402a — KG Hinglish bridge (2,463 terms) + Aksharantar (3,660) supersede the manual 300-entry plan |
| T400 | Qdrant vector DB setup | S | Deferred — in-memory numpy embeddings give <10ms retrieval at 27K docs; Qdrant adds value at 100K+ scale or for horizontal scaling |
| T401 | FastAPI `/search` endpoint | M | ✅ Done 2026-04-14 (`d541cea`) — Swagger + CORS + lifespan warm-up; 37-140ms warm latency |
| T403 | Query preprocessor (lang detect, spelling, vehicle extract) | M | Partially done — query_classifier handles lang detect + vehicle hints; spell correction deferred (BM25 typo tolerance covers it for now) |
| T404 | Fitment filter (soft boost, not hard filter) | M | P1 — unblocked by T405 metadata |
| T405 | Catalog ingestion (25K scraped products) | M | ✅ Done 2026-04-14 (`14ddb82`) — 25,952 docs; part-number extraction regex; filterable attrs |
| T406 | Zero-result analytics | M | P1 — needs logging layer first |
| T407 | Reranker layer (Cohere Rerank or cross-encoder) | M | P2 — revisit after T305 external bench tells us if rerank is worth building |
| T408 | Load testing (target p95 <200ms) | M | P1 — warm p50 ~60ms already; formal p95 test pending Hetzner deploy |
| T409 | Deploy to Railway/Render | M | ✅ Partial — Cloudflare Tunnel (ephemeral) live. Named tunnel pending domain decision. Hetzner move deferred to first pilot. |
| T410 | Multi-tenant `/demo/catalog` + per-session index | M | ✅ Done 2026-04-14 (`4174b5f`) — per-session Meilisearch index + v3 embeddings |
| T411 | Async job flow for large catalogs (up to 500K SKUs) | M | ✅ Done 2026-04-14 (`ab4339f`) — start+batch+commit+URL ingest |
| T412 | Concierge CLI (`prepare_demo.py`) + named slugs + /try HTML UI | L | ✅ Done 2026-04-14 (`1311a27`) — CSV/XLSX/JSON/folder/URL + pandas parsing + vanilla-JS UI |
| T413 | Concierge guide + `/demo` Claude skill + `/demo` slash command | S | ✅ Done 2026-04-15 (`fadf077`) |
| T414 | Per-session API key auth + `/catalog/try` public dashboard | M | ✅ Done 2026-04-15 (`f7c6e6d`) — `?key=` or X-API-Key header; Badho-Search-style faceted UI |
| T305 | External benchmark (v3 vs OpenAI text-embedding-3-large + Cohere embed-multilingual-v3 + jina-v3) | M | **Surfaced by user's friend 2026-04-15.** Execute before LinkedIn post for credibility. ~$2 API cost + 2 hr. Propose ~8 metrics (not 30): graded nDCG@10, Recall@5, 6-type zero-rate, latency p50/p95, cost/1K. |
| T-named-tunnel | Named Cloudflare tunnel on `search.whileyousleep.xyz` | S | P0 — 15 min, $0. Unblocks LinkedIn post. |

### Phase 6: Product + GTM

**GTM tasks unblocked from technical dependencies (ADR 011).**

| ID | Task | Size | Priority |
|----|------|------|----------|
| T505 | Identify 5 target mid-market Indian auto-parts prospects | M | P0 | ✅ a4eb69d (Pikpart, AutoDukan, Parts Big Boss top 3; report in context/research/t505-prospects-2026-04-12.md) |
| T506a | Notebook-based search audit (no API needed — `text-embedding-3-large` + prospect CSV + their queries) | S | P0 | ✅ 775e446 (notebooks/search_audit.ipynb) |
| T506 | Deliver 3 free audits to prospects | L | P0 | Blocked (user outreach) |
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
