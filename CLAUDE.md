# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

Domain-specific embedding model training pipeline for Indian auto parts search. The goal is to build a search API that handles Hindi/Hinglish queries, misspellings, symptom-based search, and part number cross-references — things no Indian auto parts platform currently supports.

Research data lives in a sibling directory: `../auto-parts-research/` (6 reports covering 98 platforms, vocabulary, competitive landscape).

## Project Structure

```
context/               # Product & project management
  PRODUCT.md           # Vision, problem, solution, moat, metrics
  ROADMAP.md           # 6-phase plan with status tracking
  plans/               # Per-phase implementation plans
  decisions/           # Numbered ADRs (architecture decision records)
  research/            # Source index, links to research reports
memory/                # Learnings & discoveries (things not obvious from code)
docs/                  # Future: API docs, integration guides
auto_parts_search/     # Core Python package
scrapers/              # Platform scrapers
training/              # Training data generators
tests/                 # pytest suite
data/
  raw/                 # Scraped products (gitignored, ~1.4M records)
  training/            # Generated pairs + benchmark (committed)
  knowledge_graph/     # Phase 2 output (gitignored)
```

Read `context/ROADMAP.md` for current phase and what's next. Read `memory/learnings.md` for non-obvious discoveries. Read `context/decisions/` for why things are built the way they are.

## Commands

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run a single test file
python3 -m pytest tests/test_vocabulary_pairs.py -v

# CLI pipeline
python3 -m auto_parts_search scrape      # Run Shopify + Playwright scrapers
python3 -m auto_parts_search pairs       # Generate training pairs (vocab + catalog)
python3 -m auto_parts_search benchmark   # Generate 195-query evaluation benchmark
python3 -m auto_parts_search stats       # Show data file counts
python3 -m auto_parts_search all         # Run everything in sequence

# Run scrapers individually
python3 -c "from scrapers.shopify_scraper import scrape_all_shopify; scrape_all_shopify()"
```

Playwright scrapers require: `python3 -m playwright install chromium`

## Architecture

Three independent modules that feed into a pipeline:

**`auto_parts_search/`** — Core package
- `config.py` — All paths, scraping targets, and constants. `RESEARCH_DIR` points to `../auto-parts-research/`.
- `schemas.py` — Three dataclasses: `Product` (normalized catalog item), `TrainingPair` (text_a/text_b/label for sentence-transformers), `BenchmarkQuery` (eval query with expected results).
- `__main__.py` — CLI dispatcher. Commands map to `cmd_scrape()`, `cmd_pairs()`, `cmd_benchmark()`, `cmd_stats()`.

**`scrapers/`** — Product data collection (outputs to `data/raw/*.jsonl`)
- `shopify_scraper.py` — Uses public `/products.json` endpoint. Targets: SparesHub, Bikespares.in, eAuto. Paginates with 2s delay, extracts vehicle info from Shopify tags.
- `playwright_scraper.py` — Headless browser scrapers for Boodmo (Angular SPA) and Autozilla (Magento). Uses CSS selector extraction. Boodmo's best data source turned out to be sitemap parsing (1.4M part URLs from `/sitemaps/sitemap_parts_*.xml`).

**`training/`** — Training data generation (outputs to `data/training/`)
- `vocabulary_pairs.py` — Generates pairs from hardcoded vocabulary tables extracted from research: Hindi↔English synonyms, misspellings, symptom→part mappings, brand-as-generic. Produces ~1,600 pairs. No network calls.
- `catalog_pairs.py` — Generates pairs from scraped product JSONL files. Groups products by `category|vehicle_make|vehicle_model`, creates positive pairs within groups and negative pairs across groups.
- `benchmark.py` — 195 curated test queries across 6 types (exact English, Hindi/Hinglish, misspelled, symptom, part number, brand-as-generic) with expected results and difficulty ratings.

## Data Flow

```
Scrapers → data/raw/*.jsonl (Product JSONL)
                ↓
vocabulary_pairs.py → data/training/vocabulary_pairs.jsonl
catalog_pairs.py   → data/training/catalog_pairs.jsonl
(merged)           → data/training/all_pairs.jsonl
benchmark.py       → data/training/benchmark.json
```

`data/raw/` is gitignored (scraped data, ~1.4M records). `data/training/` is committed (generated pairs + benchmark).

## Key Design Decisions

- All scraped products normalize to the `Product` dataclass regardless of source platform. The `source` field tracks origin.
- Training pairs use binary labels (1.0/0.0) with a 2:1 negative:positive ratio. Pair types: `synonym`, `misspelling`, `symptom`, `brand_generic`, `catalog_positive`, `catalog_negative`, `negative`.
- Shopify scraper uses `products.json` API (no auth needed). Playwright scraper is a fallback for JS-rendered sites.
- Boodmo's Angular SPA uses signed API headers (`x-boo-sign` HMAC per request). Direct API calls fail — must use browser context or sitemap parsing.

## Planned But Not Yet Built

- **Knowledge graph** from government sources: HSN code taxonomy (CBIC), DGT ITI mechanic syllabi (part→system→symptom chains), NHTSA vehicle API (free JSON, no auth), ASDC qualification packs, TecDoc cross-references.
- **Embedding model fine-tuning** using sentence-transformers on the training pairs.
- **Hybrid search system** combining embeddings + keyword search + fitment filtering.
- **FastAPI endpoint** for search-as-a-service.
