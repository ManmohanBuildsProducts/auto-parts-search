# Product: Auto Parts Search Intelligence

## One-liner
Domain-specific search API for Indian auto parts that handles Hindi/Hinglish, misspellings, symptom-based queries, and part number cross-references.

## Problem
Zero Indian auto parts platforms support Hindi search, semantic search, or symptom-based search. Even Boodmo (13M SKUs, $54M revenue) uses basic keyword + vehicle dropdown. Mechanics searching "brake ki patti" or "engine garam ho raha hai" get zero results everywhere.

## Solution
A hosted search API that auto parts platforms plug into their existing stack. Powered by a domain-specific embedding model trained on Indian auto parts vocabulary + a knowledge graph of part relationships.

## Target Customer
Mid-market Indian auto parts e-commerce platforms (Koovers, SparesHub, Autozilla-tier). Too big for basic search, too small to build ML teams. Also: Shopify-based auto parts stores (one-click app install).

## Revenue Model
- Startup: Free (10K queries/month)
- Growth: Rs.8K-25K/month (100K-500K queries)
- Enterprise: Custom

## Competitive Landscape
- **No direct competitor in India** (as of April 2026)
- PartsLogic (US, 2 employees, no India/Hindi)
- Algolia Auto Parts (March 2026, enterprise-only, requires ACES/PIES data Indians don't have)
- TecDoc has only 92 Indian manufacturers catalogued
- GoMechanic Spares is dead (fraud → fire sale → shutdown)

## Defensible Moat
1. Indian auto parts knowledge graph (HSN taxonomy + DGT syllabi + vocabulary)
2. Hindi/Hinglish training data (not replicable by Western search companies)
3. Fitment database for Indian vehicles (Maruti/Tata/Mahindra models that TecDoc barely covers)
4. Customer search logs → demand intelligence (compounds over time)

## Key Metrics
- Search success rate (% queries returning relevant results)
- Zero-result rate
- Search-to-purchase conversion lift vs customer's existing search
- Latency (p95 < 200ms)
