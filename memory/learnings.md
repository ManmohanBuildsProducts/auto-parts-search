# Learnings & Discoveries

Things we discovered during research and building that weren't obvious upfront.

## Origin Context
- This project originated from evaluating a friend's food embedding model business. He scraped food delivery app data, built domain-specific embeddings for food search, and sells the API to smaller platforms. We validated the approach works, then identified auto parts as a higher-TAM, more defensible vertical to build independently.
- The food embedding model serves as a reference implementation — same architecture (fine-tuned sentence-transformers, API endpoint), different domain data.

## Market
- **GoMechanic Spares is dead** (April 2026). Cofounders hit with fraud FIR, company fire-sold to Servizzy for Rs.220 Cr. Spares section is abandoned — `/spares/` URL times out, zero links from homepage. Don't target them as customer or competitor.
- **Boodmo is the market leader** at 13M SKUs, $54M revenue, 11M app downloads. But their Angular SPA + signed API headers make scraping extremely difficult. Sitemap parsing (1.4M URLs) was the breakthrough.
- **SparesHub is actually a Skoda specialist** — 12,500 of their products are Skoda genuine parts. Their Shopify catalog is misleadingly narrow despite the generic name.
- **Two-wheelers dominate** — 260M 2W vs 50M 4W on Indian roads. Hero Splendor has 30-40M cumulative units. Honda Activa has 32M+. Parts for these models are the highest-volume SKUs.

## Technical
- **Shopify products.json is the easiest scraping target** — public, paginated, JSON, no auth. Works on any Shopify store. 250 items per page, paginate until empty.
- **Boodmo uses Firebase App Check + HMAC-signed headers** (`x-boo-sign`). Each API request requires a unique signature. Direct API calls return 401 ("DenyWithoutRequiredHeaders"). Must use browser context or sitemaps.
- **Boodmo's sitemap has 36 part XML files** with 40K URLs each = 1.4M total. URL format: `/catalog/part-{name}-{id}/`. No vehicle info in URLs but part names are well-structured.
- **Autozilla (Magento)** returns exactly 12 items per search page. No pagination controls visible in DOM for headless scraping.

## Vocabulary
- **Indian English is British-derived**: "silencer" not "muffler", "bonnet" not "hood", "dickey" not "trunk", "stepney" not "spare tire".
- **Three vocabulary layers**: British-inherited English → Hinglish phonetic ("shocker", "self", "dynamo") → brand-as-generic ("Mobil" = any engine oil, "Exide" = any battery).
- **"break pad" is the #1 misspelling** — brake/break confusion is universal.
- **Symptom-first search is critical** — non-technical users search by experience: "steering bhaari", "engine garam", "brake lagane par khar-khar". No Indian platform handles this.

## Data Architecture
- **Catalog scraping alone gives volume but not relationships**. 1.4M part names from Boodmo are vocabulary data, not relationship data. Need knowledge graph from structured sources.
- **HSN codes ARE the official taxonomy** — every auto part in India has a mandatory HSN code for GST. Chapter 8708 hierarchy maps directly to our category structure.
- **DGT ITI mechanic syllabi are the richest single source** for part-system-symptom relationships. 6 free PDFs covering IC engines, brakes, suspension, electrical, diesel, EV.
- **NHTSA API is free and gives vehicle-part cross-references** — recall data maps specific parts to specific vehicle models. Even though US-focused, Honda/Hyundai/Toyota/Suzuki models overlap with India.

## Risks & Legal
- **Scraping ToS risk**: Scraping Boodmo/Autozilla likely violates their ToS. Mitigation: train model on scraped data (more defensible than reselling data), don't use competitor brand names in marketing, build original dataset from government sources (HSN, DGT) over time.
- **IndiaMART is an untapped data source**: India's largest B2B marketplace with massive auto parts section — hasn't been scraped yet. Could significantly increase training data volume.
- **Algolia is the incoming threat**: Launched auto parts solution March 2026. Enterprise-priced, requires ACES/PIES data (Indians don't have), no Hindi. Monitor their India moves quarterly.

## Sales Insight
- **30% of auto parts returns are caused by wrong fitment** — industry stat from platform audit. This is the cost of bad search. Use in every sales pitch.
- **OEM direct portals are dual-opportunity**: 9 identified (Maruti, Tata, Hero, TVS, RE, Yamaha, Bajaj, Hyundai Mobis, BharatBenz). They are both (a) enterprise sales targets (huge volume, basic search) and (b) data sources (structured product catalogs).
- **Koovers (Schaeffler-backed) grew 2.5x revenue YoY to Rs.198 Cr** — fastest-growing B2B auto parts platform. Prime target customer.
