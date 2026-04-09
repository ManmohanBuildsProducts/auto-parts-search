# Decision 002: Data Source Strategy

**Date**: 2026-04-09
**Status**: Decided

## Context
Need large-scale structured data about Indian auto parts. Scraped catalog data gives product names but lacks relationships (part-to-system, part-to-vehicle, part-to-symptom).

## Decision
Combine three data layers:

1. **Scraped catalogs** (volume) — 1.4M Boodmo sitemap URLs + 25K Shopify products
2. **Government/institutional sources** (structure) — HSN codes, DGT ITI syllabi, NHTSA API, ASDC qual packs
3. **Vocabulary research** (language) — Hindi/English mappings, misspellings, mechanic slang

## Key Sources Evaluated

| Source | Accessible | Value | Notes |
|---|---|---|---|
| Boodmo sitemap | Yes (public XML) | 1.4M part names | No vehicle info in URLs |
| Shopify stores | Yes (products.json) | 25K with vehicle data | SparesHub, Bikespares, eAuto |
| GoMechanic | Dead | N/A | Fraud scandal, spares section shutdown |
| HSN Code DB | Yes (ClearTax etc.) | Official taxonomy | Chapter 87/84/85 |
| DGT ITI syllabi | Yes (free PDFs) | Part-system-symptom chains | 6 curricula on dgt.gov.in |
| NHTSA vPIC API | Yes (free, no auth) | Vehicle-part cross-refs | US data, but overlapping vehicle models |
| TecDoc | Paid (RapidAPI option) | Cross-references | Only 92 Indian manufacturers |
| ASDC Qual Packs | Yes (free PDFs) | Task-part mappings | 200+ job roles |

## Rejected
- GoMechanic Spares: dead
- Direct Boodmo API: requires per-request HMAC signing, not feasible without reverse-engineering
- Flipkart/Amazon auto: massive but generic catalog, low signal-to-noise for domain training
