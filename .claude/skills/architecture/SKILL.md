---
name: architecture
description: Use when editing scrapers, knowledge-graph assembly, training-pair generators, the SQLite graph DB, the Product dataclass, or anything touching the data pipeline from raw catalogs through training pairs to benchmark. Covers module responsibilities, data flow, design decisions, and known gotchas (Boodmo HMAC signing, Shopify pagination, Playwright-as-fallback).
---

# Auto Parts Search — Architecture

Load this skill before editing any of: `scrapers/`, `auto_parts_search/`, `training/`, the SQLite graph DB, or the data pipeline flow.

## Three independent modules that feed into a pipeline

### `auto_parts_search/` — Core package
- `config.py` — all paths, scraping targets, constants. `RESEARCH_DIR` points to `../auto-parts-research/`. Also defines `GRAPH_DB`, `TRAINING_GOLDEN_DIR`, `TRAINING_EXPERIMENTS_DIR`, `RANDOM_SEED=42` (ADR 009).
- `schemas.py` — three dataclasses: `Product` (normalized catalog item), `TrainingPair` (text_a/text_b/label for sentence-transformers), `BenchmarkQuery` (eval query with expected results).
- `build_graph.py` — assembles the knowledge graph dict from JSON source files (HSN, ITI, NHTSA, ASDC, vocabulary). Output shape: `{metadata, nodes: [dict], edges: [dict]}`. Node keys: `id`, `node_type`, `name`, `aliases`, `provenance.source`. Edge keys: `source_id`, `target_id`, `edge_type`, `source`, `confidence`.
- `graph_db.py` — SQLite-backed storage for the assembled graph (ADR 007). `GraphDB` class with `load_from_graph_dict`, `neighbors`, `parts_in_system`, `symptoms_for_part`, `compatible_vehicles`, `cross_references`, FTS5 `search`, `counts`. Context-manager API.
- `__main__.py` — CLI dispatcher. Commands: `scrape`, `pairs`, `benchmark`, `graph`, `build-graph-db`, `stats`, `all`.

### `scrapers/` — Product data collection
Outputs to `data/raw/*.jsonl` (gitignored).

- `shopify_scraper.py` — public `/products.json` endpoint. Targets: SparesHub, Bikespares.in, eAuto. Paginates with 2s delay (`REQUEST_DELAY` in config). Extracts vehicle info from Shopify tags. 250 items per page, paginate until empty.
- `playwright_scraper.py` — headless browser for Boodmo (Angular SPA) and Autozilla (Magento). CSS selector extraction. **Boodmo's primary data source is actually sitemap parsing** (1.4M part URLs from `/sitemaps/sitemap_parts_*.xml`), not the browser scraper.
- `hsn_scraper.py` — CBIC HSN code taxonomy, chapter 8708 + 84 + 85. Output: `data/knowledge_graph/hsn_taxonomy.json` (1,918 codes).
- `iti_scraper.py` + `iti_systems_parser.py` — DGT ITI syllabi. **⚠ Currently ~95% hand-curated in Python (see ADR 008).** PDFs downloaded but gitignored until T101b commits them; real content lives in `VEHICLE_SYSTEMS` and `STRUCTURED_DIAGNOSTICS` hardcoded dicts. Planned re-extraction via LLM (T102b/T103b) will add provenance fields.
- `nhtsa_scraper.py` + `nhtsa_vehicle_scraper.py` — NHTSA vPIC API (free, no auth) for vehicle taxonomy + recall data.
- `asdc_scraper.py` — ASDC qualification packs (PDF download + parse).

### `training/` — Training pair generation
Outputs to `data/training/*.jsonl`. Golden reference in `data/training/golden/`; experiments in `data/training/experiments/<date>-<hypothesis>/` (gitignored).

- `vocabulary_pairs.py` — pairs from hardcoded vocabulary tables (Hindi↔English synonyms, misspellings, symptom→part mappings, brand-as-generic). ~1,600 pairs. No network calls. **Uses `rng = random.Random(seed)` pattern for deterministic negative sampling.**
- `catalog_pairs.py` — pairs from scraped product JSONL. Groups by `category|vehicle_make|vehicle_model`, positive pairs within groups, negative pairs across. **Uses module-level `random.seed(RANDOM_SEED)` — weaker than vocabulary's per-function `rng`; upgrade pending.**
- `benchmark.py` — 195 curated test queries across 6 types. Does not use `random`.

## Data flow

```
┌─────────────────────────────────────────────────────────────┐
│ Scrapers → data/raw/*.jsonl (Product JSONL, gitignored)     │
│                       ↓                                      │
│         ┌─────────────┴─────────────┐                       │
│         ↓                           ↓                       │
│  vocabulary_pairs.py         catalog_pairs.py                │
│         ↓                           ↓                       │
│  data/training/golden/       data/training/golden/           │
│  vocabulary_pairs.jsonl      catalog_pairs.jsonl             │
│         └─────────────┬─────────────┘                       │
│                       ↓                                      │
│           data/training/golden/all_pairs.jsonl              │
│                                                              │
│  Separately:                                                 │
│  HSN + ITI + NHTSA + ASDC JSON → build_graph.py →           │
│    data/knowledge_graph/graph.db (SQLite, derived, ignored)  │
│                                                              │
│  benchmark.py → data/training/golden/benchmark.json         │
└─────────────────────────────────────────────────────────────┘
```

## Key design decisions (cite ADRs before modifying)

- **Product dataclass normalization.** All scraped products → `Product` regardless of source. `source` field tracks origin. (Pre-audit, no ADR.)
- **Binary labels for training pairs.** 1.0/0.0 with 2:1 negative:positive ratio. Pair types: `synonym`, `misspelling`, `symptom`, `brand_generic`, `catalog_positive`, `catalog_negative`, `negative`. **Graded labels coming in Phase 3** (ADR 006, ADR 013 when written).
- **SQLite for knowledge graph.** JSON files = committed inputs; `.db` = derived, gitignored, rebuilt via `build-graph-db` CLI. Depth-1/2 traversals only; no graph DB needed (ADR 007).
- **TASKS.md is the single task-board source.** Cline Kanban deprecated (ADR 005).
- **Phase 3 = closed-loop `(pair_strategy, model, benchmark)` triples.** No open-loop pair generation (ADR 006).
- **Reproducibility = MANIFEST + seed + golden/experiments dirs.** Bit-identical rerun from cold clone is a property we claim (ADR 009).

## Known gotchas (domain-level — surface these early)

- **Boodmo uses Firebase App Check + HMAC-signed headers** (`x-boo-sign`). Direct API calls return 401. Use browser context or the sitemap parse. (`memory/learnings.md`.)
- **Shopify `/products.json` endpoint is public** on any store, 250 items/page, paginate until empty. No auth.
- **Autozilla (Magento) returns exactly 12 items/search page**; no DOM pagination controls visible to Playwright.
- **DGT ITI PDFs are textual (not scanned)** — `pdftotext` works. The current parser runs on zero PDFs because `.gitignore` excluded them before ADR 008's fix; LLM re-extraction is T102b/T103b.
- **`random` state drift**: module-level `random.seed()` in `catalog_pairs.py` can be polluted if anything else calls `random.*` first. Upgrade to per-function `rng = random.Random(42)` (same pattern as `vocabulary_pairs.py`).

## Planned but not yet built

- **Embedding model fine-tuning** using sentence-transformers on the graded pair set (Phase 3 training loop, `context/plans/phase3-training-loop.md`).
- **Hybrid search system** combining embeddings + keyword (Meilisearch) + fitment filtering + query classifier (Phase 5; tokenizer per ADR 010).
- **FastAPI endpoint** for search-as-a-service (Phase 5).
- **GTM notebook audit** (T506a) — the highest-leverage unblock per ADR 011.
