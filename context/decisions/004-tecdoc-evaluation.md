# Decision 004: TecDoc RapidAPI Free Tier Evaluation

**Date**: 2026-04-10
**Status**: Decided

## Context

Our knowledge graph (Decision 003) needs cross-reference data: OEM part number to aftermarket equivalents. TecDoc is the industry standard catalog for automotive aftermarket parts — 1,000+ brands, 190,000+ vehicle types, 9.8M+ articles. We evaluated whether the free tier of the TecDoc Catalog API on RapidAPI is useful for bootstrapping our knowledge graph.

## What We Found

### API Availability

Two TecDoc-related APIs exist on RapidAPI:

1. **TecDoc Catalog** by `ronhartman` — 2,455 subscribers, 3/5 rating (105 reviews), 9.9 popularity, 100% service level, 321ms avg latency. This is the primary option.
2. **Auto Parts Catalog** by `makingdatameaningful` — same underlying provider, also available on Apify ($69/mo + usage).

We evaluated #1 (ronhartman) as the primary candidate.

### Pricing Tiers

| Tier | Price | Requests/Month | Rate Limit | Hard Limit? |
|------|-------|----------------|------------|-------------|
| **Basic (Free)** | $0/mo | 100 | 5 req/sec | Yes |
| Pro | $29/mo | 20,000 | 15 req/sec | Yes |
| Ultra | $49/mo | 100,000 | 20 req/sec | Yes |
| Mega | $299/mo | 1,000,000 | 50 req/sec | Yes |

All tiers include 10,240MB/mo bandwidth + $0.001/MB overage. All limits are hard (requests fail after quota).

### Available Endpoints (v2, All Tiers)

**Languages & Countries** (5 endpoints)
- `GET /languages/list` — All available languages
- `GET /countries/list` — All available countries
- `GET /languages/get-language/lang-id/{langId}` — Language details
- `GET /countries/list-countries-by-lang-id/{langId}` — Countries by language
- `GET /countries/get-country/lang-id/{langId}/country-filter-id/{countryFilterId}` — Country details

**Manufacturers** (collapsed group — list and lookup by ID)
- `GET /manufacturers/find-by-id/{manufacturerId}` — Manufacturer details

**Models** (list models by manufacturer)
- `GET /models/list/manufacturer-id/{manufacturerId}/lang-id/{langId}/country-filter-id/{countryFilterId}/type-id/{typeId}`

**Vehicles** (vehicle type details, engine types)
- `GET /types/list-vehicles-type` — All vehicle types
- `GET /types/vehicle-type-details/{vehicleId}/...` — Detailed vehicle info
- `GET /types/list-vehicles-types/{modelSeriesId}/...` — Engine types for model

**Part Identifier (by ArticleNo)** — Search parts by article number
- `GET /articles/search/lang-id/{langId}/article-search/{articleSearchNr}`
- `GET /articles/search/lang-id/{langId}/supplier-id/{supplierId}/article-search/{articleSearchNr}`

**OEM Identifier** — Look up OEM numbers for a part
- `POST /oem/get-oem-by-article-id` — Get OEM number(s) for an article

**Part Info (by Article ID)** — Full article details
- `GET /articles/article-id-details/{articleId}/lang-id/{langId}/country-filter-id/{countryFilterId}`
- `GET /articles/article-number-details/lang-id/{langId}/country-filter-id/{countryFilterId}/article-no/{articleNo}`
- `GET /articles/article-all-media-info/{articleId}/lang-id/{langId}` — Images/media

**Parts Cross Reference (6 endpoints)** — The most valuable group for us:
- `GET /cross-references/by-article-id/{articleId}` — Cross-refs for an article
- `GET /cross-references/equivalent-oem-numbers` — Find equivalent OEM numbers
- `GET /cross-references/by-article-no/{articleNo}` — Cross-refs by article number
- `GET /cross-references/oem-numbers-by-article-id/{articleId}` — OEM cross-refs
- `POST /cross-references/equivalent-oem-numbers` — Batch OEM lookup
- `GET /cross-references/oe-number-by-article-id/{articleId}` — OE number lookup

**Category & Product Groups** (3 variants for category/product group trees by vehicle)
- `GET /category/category-products-groups-variant-{1,2,3}/{vehicleId}/...`

**VIN Decoding** (3 versions)
- `GET /vin/decoder-v1/{vinNo}` — Basic VIN decode
- `GET /vin/decoder-v2/{vinNo}` — Extended VIN decode
- `GET /vin/decoder-v3/{vinNo}` — Beta, most detailed

### What Cross-Reference Data Looks Like

Based on TecDoc's data model, cross-references link:
- **Aftermarket article number** (e.g., Bosch F002H234FF) to **OEM number** (e.g., Maruti 16510M68K00)
- **Aftermarket article** to **other aftermarket equivalents** across brands
- Each link includes supplier/brand info, article number, and compatibility metadata

This maps directly to our knowledge graph's `equivalent_to` edge type.

## Analysis: Is 100 Requests/Month Useful?

### What 100 Requests Gets Us

With strategic use, 100 requests can pull:
- ~10 requests for reference data (manufacturers, languages, countries)
- ~20 requests for top part categories (brake pads, oil filters, etc.)
- ~70 requests for cross-references on specific articles

That's enough to **validate the data model and sample cross-references for ~70 parts** — sufficient for proof-of-concept, not for building the full graph.

### Request Budget for Top 20 Part Types

| Step | Requests | Purpose |
|------|----------|---------|
| Get manufacturers list | 1 | Identify Bosch, Denso, Mann, etc. |
| Get categories for a vehicle | 3 | Map category tree for 3 vehicles |
| Search articles by number | 20 | Look up 20 known part numbers |
| Get cross-references | 40 | Cross-refs for 20 articles (2 endpoints each) |
| Get OEM equivalents | 20 | OEM numbers for those 20 articles |
| Buffer | 16 | Retry failed requests |
| **Total** | **100** | **20 part types sampled** |

### Indian Market Coverage

TecDoc's coverage is **Europe-centric**. Key concerns for Indian market:
- Strong coverage: Bosch, Denso, Mann+Hummel, NGK, Gates — these brands sell in India
- Weak coverage: Maruti Genuine, TATA Genuine, Mahindra OEM parts — Indian OEMs are not well-represented in TecDoc
- Missing: Most Indian aftermarket brands (Rane, Minda, Lumax, Valeo India-specific SKUs) are unlikely to be in TecDoc
- Vehicle types use KType system — Indian-market-specific variants (e.g., Maruti Alto K10 BS6) may not have KType mappings

### Comparison with Official TecDoc Access

| | RapidAPI Free | RapidAPI Pro | Official TecAlliance API |
|---|---|---|---|
| Cost | $0/mo | $29/mo | ~EUR 219/yr + custom pricing |
| Requests | 100/mo | 20,000/mo | Based on license |
| Data | Same TecDoc DB | Same | Full Pegasus 3.0 API |
| Indian coverage | Limited | Limited | Same — TecDoc is EU-focused |
| Cross-refs | Yes | Yes | Yes, with more search patterns |

## Decision

**Use the free tier for validation only.** It is useful for:

1. **Validating our graph schema** — Confirm that TecDoc's cross-reference structure maps to our `equivalent_to` edges
2. **Sampling 20 top part types** — Pull real cross-references for brake pads, oil filters, spark plugs, etc.
3. **Evaluating Indian market coverage gaps** — Quantify what percentage of our catalog would have TecDoc matches

**Do NOT plan to use TecDoc as a primary data source for the Indian market.** The coverage gap for Indian OEM and aftermarket brands is a fundamental limitation that no pricing tier fixes.

### Important Caveats

- **All RapidAPI TecDoc listings are third-party wrappers**, not official TecAlliance APIs. The main providers (ronhartman, makingdatameaningful) wrap the same underlying TecDoc dataset. None are operated by TecAlliance.
- **Official TecAlliance OneDB API requires enterprise licensing** — no self-serve signup. For production use, contact TecAlliance India: Ravish Deshpande (+91 70281 28132).
- **TecAlliance claims ~100 Indian aftermarket brands** in their catalog and has an active India team, but Indian OEMs (Hero, Bajaj, TVS, Maruti) are not listed as TecDoc data suppliers, confirming the OEM cross-reference gap.
- **VIN-based lookup is explicitly European-only** — VIN decode endpoints won't resolve Indian-market VINs.

### Alternative Worth Investigating

**Autorox API** (autorox.ai) — Indian-built auto parts platform with native vehicle coverage for Hero, Bajaj, TVS, Maruti, and other Indian OEMs. Worth evaluating as a complementary or primary data source for Indian-market cross-references where TecDoc falls short.

### Recommended Next Steps

1. Sign up for free tier, pull sample data for 20 part types (see budget table above)
2. Cross-check TecDoc article numbers against our scraped Boodmo/Autozilla data to measure overlap
3. If overlap > 30%, consider Pro tier ($29/mo) for a one-time bulk extraction
4. **Evaluate Autorox API** for Indian-market OEM cross-references (separate decision doc)
5. For Indian-specific cross-references, prioritize Boodmo's own cross-reference data (already in our scraper) and manual curation from mechanic knowledge

## Impact on Knowledge Graph

TecDoc cross-references feed the `equivalent_to` edge type. Even with limited Indian coverage, the international brand cross-references (Bosch ↔ Denso ↔ NGK for spark plugs, etc.) are valuable for:
- Training data: generating `equivalent_to` training pairs for the embedding model
- Fallback search: when a user searches an OEM number, we can suggest aftermarket alternatives
- Category validation: TecDoc's product group taxonomy is a useful reference for our own category hierarchy
