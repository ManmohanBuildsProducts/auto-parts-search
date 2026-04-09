# Learnings & Discoveries

Things we discovered during research and building that weren't obvious upfront.

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
