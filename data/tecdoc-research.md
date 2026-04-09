# Research: TecDoc Catalog APIs on RapidAPI

**Date:** 2026-04-10
**Depth:** Deep dive
**Query:** TecDoc catalog API on RapidAPI — listings, free tier, endpoints, pricing, data quality, Indian market coverage, and alternatives

---

## TLDR

There are 5–6 distinct TecDoc-related APIs on RapidAPI ranging from K-type vehicle lookup wrappers to full parts-catalog APIs. Free tiers are extremely limited (10–100 requests/month), making them unsuitable for bulk knowledge-graph construction. The official TecAlliance TecDoc API requires a paid enterprise license and is not available via RapidAPI — it must be accessed directly through TecAlliance. India is a supported market with ~100 aftermarket brands and coverage across passenger cars, commercial vehicles, and two-wheelers, but two-wheeler depth is unconfirmed.

---

## Key Findings

- There are at least 5 TecDoc-related API listings on RapidAPI, all operated by third-party resellers — none are the official TecAlliance API. [^1][^2]
- The one pricing page that rendered (Ktype Finder Tecdoc) shows: Free = 10 req/month, Pro = $59/month (600 req), Ultra = $199/month (5,000 req), Mega = $299/month (10,000 req), with $0.10/req overage. [^3]
- The most capable RapidAPI listing (Auto Parts Catalog by makingdatameaningful) exposes a hierarchical API: manufacturers → models → vehicle types → categories → articles (parts). It supports automobiles, commercial vehicles, and motorcycles. [^4]
- TecDoc K-type is the core identifier: a numeric code that uniquely identifies a vehicle's make, model, year, engine, and transmission. All parts lookups flow through K-type. [^1][^3]
- The official TecAlliance TecDoc API (OneDB) requires enterprise customer status — no self-serve free tier exists. It is a RESTful/JSON API but access requires signing a customer agreement. [^5]
- TecDoc India coverage: ~100 aftermarket brands, covers passenger cars, commercial vehicles, and two-wheelers. TecAlliance has an active India team and attended Automechanika New Delhi 2026. [^6]
- Indian OEMs (Hero, Bajaj, TVS, Maruti) are not listed in the official TecDoc OE cross-reference supplier list — coverage for Indian-specific parts is limited to what those ~100 aftermarket brands have submitted. [^7]
- For OEM cross-referencing: TecDoc maps IAM (independent aftermarket) part numbers to OEM numbers, but completeness for Indian-spec vehicles is uncertain. [^8]

---

## Details

### API Listings on RapidAPI

Five distinct TecDoc-related APIs were found on RapidAPI. All are third-party wrappers — none are official TecAlliance products.

#### 1. TecDoc Catalog (ronhartman)
- **URL:** https://rapidapi.com/ronhartman/api/tecdoc-catalog
- **Description:** Wraps the same Auto Parts Catalog API (by makingdatameaningful). The underlying Symfony 7.1 demo app exposes controllers for: manufacturers, models, types, categories, and articles.
- **Pricing:** Page not renderable by scraper — unknown tiers. Likely mirrors the makingdatameaningful pricing.
- **GitHub:** https://github.com/ronhartman/tecdoc-autoparts-catalog — Symfony demo app showing API integration pattern.

#### 2. Auto Parts Catalog (makingdatameaningful)
- **URL:** https://rapidapi.com/makingdatameaningful/api/auto-parts-catalog
- **Description:** The primary full-catalog API. Hierarchical lookup flow.
- **Endpoints (inferred from demo site + GitHub):**
  - `GET /manufacturers` — list car manufacturers by language, country, vehicle type
  - `GET /models` — models for a given manufacturer
  - `GET /types` — vehicle types (body style, engine, year range)
  - `GET /categories` — parts categories for a vehicle type
  - `GET /articles` — actual parts/articles for a category + vehicle
- **Vehicle types supported:** Automobile, Commercial Vehicles, Motorcycle
- **Live demo:** https://auto-parts-catalog.makingdatameaningful.com/ — shows 30+ language options, Germany as default country
- **Data shown in demo:** Bosch, Continental, Brembo, Mahle, Denso, Sachs, Delphi, Valeo — European/global aftermarket brands
- **Pricing:** Not scraped (JS-rendered). Likely same structure as K-type finder.
- **Note:** Also available as an Apify actor.

#### 3. Vehicle TecDoc (K-Type) Lookup API (Autoways)
- **URL:** https://rapidapi.com/Autoways/api/vehicle-tecdoc-k-type-lookup-api
- **Description:** Vehicle identification and K-type lookup. Can search by VIN, or navigate manufacturer → model → vehicle facet tree. Returns all vehicle info for a specific K-type.
- **Endpoints (from TecAlliance CN docs, same data layer):**
  - VIN search → returns K-type
  - Manufacturer list
  - Model list per manufacturer
  - Vehicle list per model (with engine, power, year range)
  - Part search by K-type
  - OE number search
  - Reference number search (fuzzy)
  - Part linkage search
- **Pricing:** Not rendered. Expected to be similar to K-type finder.

#### 4. Ktype Finder Tecdoc (autowaysnet)
- **URL:** https://rapidapi.com/autowaysnet/api/ktype-finder-tecdoc
- **Description:** Returns K-type from license plate or VIN. Only one endpoint documented.
- **Endpoint:** `GET /fr` — fromFrenchCarPlate — returns K-type from French plate
- **Note:** Appears to be heavily France/Europe focused. VIN support may extend to DE, AT, BE, ES, FR, IT, PT.
- **Pricing (confirmed):**

  | Tier   | Price/month | Requests/month | Overage       |
  |--------|-------------|----------------|---------------|
  | BASIC  | Free        | 10             | $0.10/req     |
  | PRO    | $59         | 600            | $0.10/req     |
  | ULTRA  | $199        | 5,000          | $0.10/req     |
  | MEGA   | $299        | 10,000         | $0.10/req     |

#### 5. VIN Decoder Support TECDOC Catalog (autowaysnet)
- **URL:** https://rapidapi.com/autowaysnet/api/vin-decoder-support-tecdoc-catalog
- **Description:** VIN → vehicle identification → K-type lookup. Supports Germany, Austria, Belgium, Spain, France, Italy, Portugal.
- **Pricing:** Not rendered.
- **Note:** India is not in the listed VIN-supported countries.

#### 6. Tecdoc API (gvidasmikalauskass)
- **URL:** https://rapidapi.com/gvidasmikalauskass/api/tecdoc-api
- **Description:** Independent TecDoc API wrapper.
- **Pricing/endpoints:** Not retrievable (JS-rendered, no cached content found).

---

### Endpoint Capabilities in Detail

Based on the TecAlliance OneDB API documentation (developer.tecalliance.cn — the same data layer all RapidAPI wrappers pull from):

**Vehicle Search:**
- Manufacturer → Model → Vehicle facet tree navigation
- VIN search → K-type (supports KType, AmParts CV, ChinaID PC, ChinaID CV)
- Filter by carId, engine code
- Returns: manuId, manuName, modId, modelName, construction type, engine specs (cylinders, ccm, liters, codes), power (HP/KW), fuel type, injection method, drive system, valve count, production years

**Parts/Articles Search:**
- By K-type → compatible articles list
- By OE number → cross-reference to IAM parts
- By reference/part number (fuzzy match)
- Part linkage search
- Returns: article number, brand, description, category, vehicle applicability, OE references, cross-references

**Supporting Lookups:**
- Countries, languages, brands, product groups, manufacturers lookups

**Cross-Reference Model:**
TecDoc maps in one direction: OEM part number → IAM (aftermarket) equivalents. The K-type is the vehicle anchor that links the OEM's Electronic Parts Catalogue (EPC) data to aftermarket supplier data. This is the core value for knowledge-graph use.

---

### Data Quality Assessment

**Strengths:**
- Industry standard — used by major European aftermarket distributors
- OEM EPC cross-references allow matching OEM numbers to compatible aftermarket alternatives
- Structured taxonomy: vehicle → system → category → article
- Multi-language (40+), multi-country
- Includes technical specs (dimensions, weight, torque values) through TecRMI add-on

**Weaknesses for Indian use-case:**
- Primary focus is European vehicles (German by default in demo)
- ~100 Indian aftermarket brands vs 1,000+ globally — coverage gap for Indian-specific variants
- Two-wheeler depth for Indian OEMs (Hero, Bajaj, TVS) is unconfirmed
- VIN-based lookup explicitly lists only European countries — Indian VINs not supported via RapidAPI wrappers
- OE cross-references depend on whether Indian OEMs have submitted data to TecAlliance — no evidence they have
- No Hindi/Hinglish language support (the 40 languages are all written scripts, not transliteration)
- Part number formats for Indian market (Boodmo numbers, OEM numbers like Honda India vs Honda Global) may not be in the database

---

### Official TecAlliance API (Non-RapidAPI)

The official path to TecDoc data bypasses RapidAPI entirely:

- **Product:** TecAlliance OneDB API
- **Protocol:** RESTful/JSON
- **Base URL:** https://onedb.tecalliance.cn/api/ (China/SEA instance), .net for global
- **Access:** Must be a paying TecAlliance customer — no self-serve tier
- **Licensing:** Enterprise agreement required. TecDoc Catalogue Classic (UI access, not API) costs ~€183–259/year for a single-user license.
- **India contact:** Ravish Deshpande, ravish.deshpande@tecalliance.net, +91 70281 28132
- **Data supplier route:** Companies can also submit their data TO TecDoc (become a "data supplier"), which is separate from consuming the API

---

### India Market Specifics

From the TecAlliance Automechanika New Delhi 2026 materials and Motor India article:

- **Coverage:** Passenger cars, commercial vehicles, and two-wheelers — all three segments covered
- **Aftermarket brands:** ~100 Indian brands in the catalogue
- **Data quality:** "Highest quality, provided and updated directly by international and local parts manufacturers"
- **VIO data:** Vehicle-in-Operation data available for Indian car park (useful for market sizing, not parts lookup)
- **OE cross-reference:** Available, but sourced from brands that have submitted to TecAlliance. Indian OEMs (Tata, Mahindra, Maruti Suzuki, Hero MotoCorp, Bajaj Auto, TVS Motor) are not publicly listed as TecDoc data suppliers — meaning their OEM part numbers may not be in the cross-reference database.
- **Integration products in India:** TecCom (B2B order/availability platform), Digital Trade Portal, e-commerce integration

**Critical gap:** The ~100 Indian brands are mostly IAM suppliers (e.g., Minda, Bosch India, Exide, CEAT, MRF) — not OEM data. This means TecDoc can tell you "this Bosch filter fits a 2019 Honda City" but probably cannot tell you "OEM part number 15400-RTA-003 is equivalent to Bosch F026407033."

---

### Pricing Summary Table

| API | Provider | Free Tier | Paid Entry | Best Tier | Notes |
|-----|----------|-----------|------------|-----------|-------|
| Ktype Finder Tecdoc | autowaysnet | 10 req/mo | $59/mo (600 req) | $299/mo (10K req) | France/Europe plates only |
| Auto Parts Catalog | makingdatameaningful | Unknown | Unknown | Unknown | Full catalog hierarchy |
| TecDoc Catalog | ronhartman | Unknown | Unknown | Unknown | Same data as above |
| Vehicle K-Type Lookup | Autoways | Unknown | Unknown | Unknown | VIN + facet tree |
| VIN Decoder + TecDoc | autowaysnet | Unknown | Unknown | Unknown | EU VINs only |
| Tecdoc API | gvidasmikalauskass | Unknown | Unknown | Unknown | Unknown scope |
| TecAlliance OneDB | Official (direct) | None | Enterprise only | Enterprise | Full dataset, India coverage |

---

### Alternatives to RapidAPI TecDoc Wrappers

**1. Apify TecDoc Actor (making-data-meaningful)**
- URL: https://apify.com/making-data-meaningful/tecdoc
- Same data as the RapidAPI listing but accessed via Apify's actor/scraper model
- Pricing model is compute-unit based (pay per run, not per request)
- May be more cost-effective for batch extraction vs per-request billing

**2. TecAlliance Direct License**
- Contact India team directly (Ravish Deshpande)
- Full dataset access including OE cross-references
- Required for any serious production use
- Likely $500–2,000+/year for API access (UI catalog is ~€200/year, API access is higher tier)

**3. ShowMeTheParts API**
- URL: https://info.showmetheparts.com/
- US-centric, but has cross-reference data
- Free API tier exists for testing
- Not relevant for Indian market

**4. AutoDNA / VehicleDatabases**
- VehicleDatabases.com has an auto parts API with OEM numbers and cross-references
- Global coverage but US/EU primary
- Has a free tier for testing

**5. CardDatabases.com Auto Parts API**
- Explicit cross-reference (OEM part numbers, compatibility, pricing)
- US market focus

**6. Autorox API (India-specific)**
- URL: https://www.autorox.ai/developers-api
- Indian-built vehicle catalog and spare parts API
- Native Indian vehicle coverage (Hero, Bajaj, TVS, Maruti, etc.)
- More relevant for Indian two-wheeler and four-wheeler data than TecDoc
- May have better Hindi/vernacular support

---

## Data Tables

### Confirmed Endpoint Data Structure (TecAlliance Vehicle Search Response)

| Field | Type | Example | Notes |
|-------|------|---------|-------|
| manuId | Integer | 16 | Manufacturer ID |
| manuName | String | "BMW" | Manufacturer name |
| modId | Integer | 1234 | Model ID |
| modelName | String | "3 Series" | Model name |
| constructionType | String | "Sedan" | Body type |
| cylinderCount | Integer | 4 | Engine cylinders |
| capacityCcm | Integer | 1998 | Engine displacement cc |
| capacityLiters | Float | 2.0 | Engine displacement L |
| engineCodes | Array[String] | ["N20B20A"] | Engine codes |
| powerHp | Integer | 184 | Peak power HP |
| powerKw | Integer | 135 | Peak power KW |
| fuelType | String | "Petrol" | Fuel |
| injectionMethod | String | "Direct" | Injection type |
| driveSystem | String | "All-wheel Drive" | Drive type |
| valvesPerCylinder | Integer | 4 | Valve count |
| yearOfConstrFrom | Integer | 2012 | Production start year |
| yearOfConstrTo | Integer | 2019 | Production end year |
| totalMatching | Integer | 45 | Pagination: result count |

### K-Type Finder Pricing (Confirmed)

| Tier | Monthly Cost | Requests/Month | Cost Per Request | Overage |
|------|-------------|----------------|------------------|---------|
| BASIC (Free) | $0 | 10 | $0 | $0.10/req |
| PRO | $59 | 600 | $0.098 | $0.10/req |
| ULTRA | $199 | 5,000 | $0.040 | $0.10/req |
| MEGA | $299 | 10,000 | $0.030 | $0.10/req |

### RapidAPI TecDoc Listings Comparison

| API Slug | Provider | Scope | Endpoints | Free Tier | India/Two-Wheeler |
|----------|----------|-------|-----------|-----------|-------------------|
| tecdoc-catalog | ronhartman | Full catalog | 5 (mfr/model/type/cat/article) | Unknown | Unknown |
| auto-parts-catalog | makingdatameaningful | Full catalog | 5 (mfr/model/type/cat/article) | Unknown | Motorcycle ✓ |
| vehicle-tecdoc-k-type-lookup-api | Autoways | K-type + parts | ~8 (VIN, facet, OE, ref, linkage) | Unknown | Unknown |
| ktype-finder-tecdoc | autowaysnet | K-type from plate | 1 (French plates) | 10 req/mo | Europe only |
| vin-decoder-support-tecdoc-catalog | autowaysnet | VIN decode + K-type | Unknown | Unknown | EU VINs only |
| tecdoc-api | gvidasmikalauskass | Unknown | Unknown | Unknown | Unknown |

---

## Gaps & Caveats

- **Pricing for 4 of 6 APIs is unknown** — RapidAPI pages are Next.js client-rendered and not accessible to scraping. The K-type finder pricing was recovered via a renderable response; others were not.
- **Free tier request counts unconfirmed for the main catalog APIs** — only K-type finder's 10 req/month free tier was confirmed. The full catalog APIs (ronhartman, makingdatameaningful) likely have similar low free-tier limits.
- **Official TecAlliance API is not on RapidAPI** — all RapidAPI listings are third-party wrappers with unknown data freshness, reliability, and terms of service compliance.
- **Indian two-wheeler OEM coverage is unconfirmed** — TecAlliance states two-wheelers are covered, but the depth of Hero/Bajaj/TVS/Royal Enfield coverage is not documented publicly.
- **No OEM cross-reference confirmed for Indian OEMs** — TecDoc's OE cross-reference requires OEMs to submit their EPC data. There is no evidence that major Indian two-wheeler OEMs (Hero MotoCorp, Bajaj Auto, TVS Motor) have done this.
- **Hindi/Hinglish language** is not in TecDoc's 40 supported languages — the catalogue uses formal written languages only.
- **Rate limits (req/sec or req/min)** are not published for any of the RapidAPI TecDoc listings.
- **Data freshness** of third-party RapidAPI wrappers is unknown — TecAlliance updates the official catalogue quarterly.
- **Autorox API** was identified as a potentially more relevant India-native alternative but not deeply researched here.

---

## Sources

[^1]: [TecDoc Catalog (ronhartman) — RapidAPI](https://rapidapi.com/ronhartman/api/tecdoc-catalog) — accessed 2026-04-10
[^2]: [Auto Parts Catalog (makingdatameaningful) — RapidAPI](https://rapidapi.com/makingdatameaningful/api/auto-parts-catalog) — accessed 2026-04-10
[^3]: [Ktype Finder Tecdoc (autowaysnet) — RapidAPI](https://rapidapi.com/autowaysnet/api/ktype-finder-tecdoc) — accessed 2026-04-10
[^4]: [GitHub — ronhartman/tecdoc-autoparts-catalog](https://github.com/ronhartman/tecdoc-autoparts-catalog) — accessed 2026-04-10
[^5]: [TecAlliance OneDB API Documentation](https://developer.tecalliance.cn/en/introduction/index.html) — accessed 2026-04-10
[^6]: [TecAlliance at Automechanika New Delhi 2026](https://www.tecalliance.net/catch-us-at-automechanika-new-delhi/) — accessed 2026-04-10
[^7]: [TecAlliance OE Reference Data](https://www.tecalliance.net/tecdoc-oe-data-2/) — accessed 2026-04-10
[^8]: [TecAlliance supporting digitisation with TecDoc — Motor India](https://www.motorindiaonline.in/tecalliance-supporting-digitisation-with-tecdoc/) — accessed 2026-04-10
[^9]: [Vehicle TecDoc K-Type Lookup API (Autoways) — RapidAPI](https://rapidapi.com/Autoways/api/vehicle-tecdoc-k-type-lookup-api) — accessed 2026-04-10
[^10]: [VIN Decoder Support TecDoc Catalog (autowaysnet) — RapidAPI](https://rapidapi.com/autowaysnet/api/vin-decoder-support-tecdoc-catalog) — accessed 2026-04-10
[^11]: [TecAlliance Vehicle Search Endpoint Docs](https://developer.tecalliance.cn/en/tecdoc-api/function/vehicle-search/index.html) — accessed 2026-04-10
[^12]: [Auto Parts Catalog Demo Site](https://auto-parts-catalog.makingdatameaningful.com/) — accessed 2026-04-10
[^13]: [TecAlliance TecDoc Catalogue Overview](https://www.tecalliance.net/tecdoc-catalogue/) — accessed 2026-04-10
[^14]: [Autorox API — Indian vehicle catalog and spare parts](https://www.autorox.ai/developers-api) — accessed 2026-04-10
[^15]: [Auto Parts Catalog — Apify TecDoc alternative](https://apify.com/making-data-meaningful/tecdoc) — accessed 2026-04-10
