---
shaping: true
diagram_not_required: true
complexity: low
reason: Single pipeline (scrape → transform → output), no UI, no multi-system integration
---

# Phase 1: Auto Parts Training Dataset — Shaping

## Requirements (R)

| ID | Requirement | Status |
|----|-------------|--------|
| R0 | Generate embedding training pairs from research data (vocabulary, misspellings, symptoms, brand-as-generic) | Core goal |
| R1 | Build scrapers for Indian auto parts platforms to collect product catalog data | Core goal |
| R2 | Create 200-query evaluation benchmark covering 6 query types | Core goal |
| R3 | Output in sentence-transformers compatible format (InputExample pairs with labels) | Must-have |
| R4 | Scrapers handle Shopify API pattern + Playwright for Angular SPAs | Must-have |
| R5 | All scraped data normalized to a common schema (name, category, vehicle, brand, part_number, description) | Must-have |
| R6 | Training pairs include negative examples (dissimilar pairs with label 0.0) | Must-have |

## Shape A: Three-module Python pipeline (selected)

| Part | Mechanism |
|------|-----------|
| **A1** | **Research-based pair generator** — Parse vocabulary tables from 03_vocabulary_taxonomy.md, generate synonym pairs, misspelling pairs, symptom-to-part pairs, brand-as-generic pairs. Pure data transform, no network. |
| **A2** | **Shopify scraper** — Use Shopify's products.json endpoint (public, no auth) for SparesHub, Bikespares.in, eAuto. Paginate, normalize to common schema. |
| **A3** | **Playwright scraper** — For Angular SPAs (Boodmo) and Magento (Autozilla). Browser-based extraction. |
| **A4** | **Catalog pair generator** — From scraped product data, generate pairs: same-category-same-vehicle = similar (1.0), different-category = dissimilar (0.0). |
| **A5** | **Benchmark generator** — 200 curated test queries across 6 types with expected results, output as JSON. |
| **A6** | **Pipeline orchestrator** — CLI entry point: `python -m auto_parts_search.run [scrape|pairs|benchmark|all]` |

## Fit Check: R × A

| Req | Requirement | Status | A |
|-----|-------------|--------|---|
| R0 | Generate embedding training pairs from research data | Core goal | ✅ |
| R1 | Build scrapers for Indian auto parts platforms | Core goal | ✅ |
| R2 | Create 200-query evaluation benchmark | Core goal | ✅ |
| R3 | sentence-transformers compatible format | Must-have | ✅ |
| R4 | Shopify API + Playwright for SPAs | Must-have | ✅ |
| R5 | Common schema normalization | Must-have | ✅ |
| R6 | Negative examples in training pairs | Must-have | ✅ |

## Assumptions (documented per /lfg)
- Python 3.11+ available
- Shopify products.json endpoint is publicly accessible (standard for Shopify stores)
- Playwright will be used for JS-rendered sites
- Training pairs output as JSONL for easy loading into sentence-transformers
- Benchmark queries manually curated from research findings
- No auth tokens needed for initial scraping targets
