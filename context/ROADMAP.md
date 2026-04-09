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
