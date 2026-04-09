# Roadmap

## Phase 1: Training Dataset Pipeline ✅ DONE (April 2026)
**Goal**: Collect product data and generate embedding model training pairs.

Delivered:
- Scrapers for 7 platforms (25K Shopify products + 1.4M Boodmo sitemap URLs)
- 18,965 training pairs (vocabulary + catalog-based)
- 195-query evaluation benchmark (6 query types)
- CLI pipeline: `python3 -m auto_parts_search [scrape|pairs|benchmark|stats]`

## Phase 2: Knowledge Graph (NEXT)
**Goal**: Build structured domain knowledge from government/educational sources.

Sources to ingest:
- [ ] HSN code taxonomy (CBIC) → category hierarchy
- [ ] DGT ITI syllabi (6 PDFs) → part-system-symptom chains
- [ ] NHTSA vPIC API → vehicle taxonomy + recall data
- [ ] ASDC qualification packs → task-part-competency mappings
- [ ] TecDoc via RapidAPI → part cross-references (evaluate free tier)

Output: Knowledge graph (JSON/SQLite) with relationships:
- PART →[is_a]→ CATEGORY
- PART →[in_system]→ SYSTEM
- SYMPTOM →[caused_by]→ PART
- PART →[fits]→ VEHICLE
- PART →[equivalent_to]→ PART
- PART →[known_as]→ ALIAS

## Phase 3: Enhanced Training Data
**Goal**: Generate high-quality training pairs from knowledge graph.

- Graded similarity (not just binary 1.0/0.0) based on graph distance
- Hierarchy pairs from HSN codes (siblings closer than cousins)
- Diagnostic chain pairs from ITI syllabi
- Compatibility pairs from NHTSA/TecDoc
- Multi-task loss functions (synonym vs hierarchy vs compatibility)

## Phase 4: Embedding Model
**Goal**: Fine-tune domain-specific embedding model.

- Base model: Jina v3 (LoRA adapters) or sentence-transformers multilingual
- Train on Phase 3 pairs
- Benchmark against: base model, OpenAI embeddings, Cohere multilingual
- Target: 20%+ improvement on our 195-query benchmark

## Phase 5: Search System
**Goal**: Build the actual search API product.

- FastAPI endpoint
- Hybrid retrieval: embedding search + keyword search (Typesense/Qdrant)
- Fitment filtering from knowledge graph
- Query preprocessing (language detection, spelling correction, vehicle extraction)
- Re-ranking

## Phase 6: Product & GTM
**Goal**: First paying customer.

- Demo UI (split-screen: their search vs ours)
- Free search audit tool (analyze customer's search logs)
- Shopify app for one-click integration
- Target 3 design partners for pilot
- OEM portals (Maruti, Tata, Hero, TVS) as enterprise prospects

## Phase 7: Expansion (Future)
**Goal**: Go global + expand verticals.

- **India → Global**: Same problem worldwide. US/EU auto parts mid-market pays 10-50x more. Reuse model architecture, retrain on English-only data for global vehicle models. Target: 12 months after first Indian customer.
- **Regional languages**: Add Tamil, Telugu, Malayalam, Bengali, Marathi. Start with South India (different mechanic vocabulary from Hindi belt). Requires new training pairs per language.
- **Two-wheeler focus**: 260M 2W vs 50M 4W in India — 2W is the volume play. Current training data is 4W-heavy (SparesHub = Skoda). Need dedicated 2W scraping and vocabulary work.
- **Adjacent verticals**: Building materials / hardware (same problem structure, India digitizing fast), pharma / nutraceuticals (Ayurvedic product search).
- **EV parts**: Growing segment. DGT has EV mechanic syllabus. 8 nascent EV parts platforms identified. Early mover advantage.

## Known Data Imbalances
- Training data is 4W-heavy: SparesHub (12.5K, mostly Skoda), Boodmo sitemap (1.4M, no vehicle info). 2W data comes from Bikespares (5.7K) and eAuto (6.6K) — significantly less.
- Hindi vocabulary is North India-centric. South Indian mechanic terminology (Tamil, Telugu) is undocumented.
- No used/refurbished parts in training data (10 platforms exist but different search challenge).
