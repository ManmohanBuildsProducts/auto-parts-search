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

## Product Pillars
1. **Search API** — The wedge. Hindi/Hinglish/symptom/misspelling-aware search endpoint. Rs.8K-25K/month.
2. **Demand Intelligence** — The real product. Analyze customer's search logs → show what their users search for but can't find → assortment recommendations, trending parts, conversion optimization. Rs.50K-75K/month.
3. **Fitment Intelligence** — Cross-reference engine. "Find the Bosch equivalent of this Maruti OEM part." Reduces 30% return rate from wrong fitment (industry stat from platform audit).

## Pricing (India)
- Free: 500 SKUs, rate-limited. Enough to prove it works.
- Growth: Rs.5K-15K/month (up to 5K SKUs)
- Pro: Rs.15K-40K/month (up to 50K SKUs)
- Enterprise: Rs.40K+/month (500K+ SKUs, custom)
- Annual discount: pay 10, get 12.

## Pricing (Global — Phase 7)
- Base: $299/month (100K queries)
- Growth: $999/month (500K queries)
- Enterprise: $2K-10K/month (custom)

## GTM Playbook
1. **Free search audit** — "Give us your search logs for 48 hrs. We'll show you revenue you're losing from failed searches." Quantified, specific, impossible to unsee.
2. **Land with search API** — Easy integration, usage-based pricing.
3. **Expand to demand intelligence** — Once processing their queries, show them assortment gaps and conversion leaks.
4. **Channel partners for scale** — Integrate with vertical platforms: Petpooja-equivalents for auto (POS/ERP providers like Unicommerce), Shopify app store for D2C stores.
5. **OEM portals as enterprise targets** — Maruti, Tata, Hero, TVS all have D2C parts stores with basic search. Enterprise deals but massive volume.

## Key Metrics
- Search success rate (% queries returning relevant results)
- Zero-result rate
- Search-to-purchase conversion lift vs customer's existing search
- Latency (p95 < 200ms)
- Revenue per customer (ARPU) — target Rs.25K+ within 6 months of onboarding
