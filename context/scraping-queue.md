# Scraping Queue & Prospect Registry

Running list of Indian auto-parts platforms that are **scraping targets**, **pilot prospects**, or both. Entries overlap on purpose — most platforms are both.

**Last updated:** 2026-04-13

Columns:
- **Domain** — canonical URL
- **Stack** — e-commerce platform / tech (informs scrape feasibility)
- **Scrape status** — ✅ done | 🟡 partial | 📋 queued | ❌ won't scrape (ToS / blocked / etc.)
- **Outreach status** — ✅ pilot signed | 🟡 contacted | 📋 queued for outreach | ❌ rejected / wrong fit
- **Priority** — P0 / P1 / P2
- **Notes**

---

## Active pilot targets (from T505 research, 2026-04-12)

| Domain | Stack | Scrape status | Outreach status | Priority | Notes |
|--------|-------|---------------|-----------------|----------|-------|
| [pikpart.com](https://pikpart.com) | Custom (B2C e-comm inc. June 2025) | 📋 queued | 📋 queued | **P0** | 2W focus, 15K mechanics in Hindi belt (UP, Bihar, Haryana). Contact: Ratan Kumar Singh (COO, IIM Indore) — [LinkedIn](https://www.linkedin.com/in/ratan-kumar-singh-a1597498/). Blank-slate search = highest-fit pilot. |
| [autodukan.com](https://autodukan.com) | Unknown; claims 2M parts | 📋 queued | 📋 queued | **P0** | $1.36M raised, 41 employees. Contact: Pranay Tagare (COO) — [LinkedIn](https://www.linkedin.com/in/pranay-tagare-b4a48913/). "AI-driven" narrative — audit is investor-update ammunition. |
| [partsbigboss.com](https://partsbigboss.com) | **GoDaddy + Zoho Desk** | 📋 queued | 📋 queued | **P0** | Rs.8.45 Cr FY25 revenue, bootstrapped. Contact: Vineet Asija (founder) — [LinkedIn](https://in.linkedin.com/in/vineet-asija-46647012). Zero search investment = fastest close. GoDaddy = sitemap.xml is likely available → easiest scrape. |
| [autozilla.co](https://www.autozilla.co) | Magento | ✅ done (pre-existing, limited) | 📋 queued (careful: Bosch 26% stake) | P1 | Hyderabad, 76% CAGR. Bosch stake flags procurement risk — discovery call before building audit. Contact: Vijay Gummadi (Crunchbase/FinalScout). |
| [mechkartz.com](https://mechkartz.com) | Unknown | 📋 queued | ❌ low contact-confidence | P2 | Gorakhpur (Tier 3 Hindi belt, perfect ICP geographically). No founder LinkedIn-indexed. Use as stretch target only if warm intro materializes. |

## Already-scraped catalogs (from Phase 1)

| Domain | Stack | Scrape status | Outreach status | Priority | Notes |
|--------|-------|---------------|-----------------|----------|-------|
| [spareshub.com](https://spareshub.com) | Shopify `/products.json` | ✅ 12,500 products | ❌ declining company (Rs.2.78 Cr revenue, 67% headcount collapse) | P2 | Skoda specialist. Kept in training data. Not a pilot target. |
| [bikespares.in](https://bikespares.in) | Shopify `/products.json` | ✅ 5,700 products | 📋 possible | P2 | 2W focus. Small; pilot-volume may be marginal. |
| [eauto.co.in](https://eauto.co.in) | Shopify `/products.json` | ✅ 6,600 products | 📋 possible | P2 | 2W. Small. |
| [boodmo.com](https://boodmo.com) | Angular SPA + HMAC-signed API | 🟡 1.4M part URLs via sitemap; no vehicle info | ❌ | P1 as reference | Market leader (13M SKUs, $54M revenue) but scraping is fragile. Not a pilot target (too big for solo founder). |

## Dropped / declined candidates (2026-04-12 research)

| Domain | Why dropped |
|--------|-------------|
| [gomechanic.in/spares](https://gomechanic.in/spares) | Dead. Cofounders in fraud FIR, company fire-sold to Servizzy; spares section is abandoned (`/spares/` URL times out). |
| [koovers.com](https://koovers.com) | Acquired by Schaeffler India 2023 (full). At 508 employees + German industrial parent, procurement flow is enterprise. Would run Schaeffler's stack. |
| [gaadizo.com](https://gaadizo.com) | Service booking, not parts catalog. Wrong product. |
| [partsavatar.ca](https://partsavatar.ca) | Canadian company; India ops are back-office only. Wrong market. |

## To investigate (next research pass)

- **OEM D2C portals** — Maruti Genuine, Tata Genuine, Hero Genuine, TVS, RE, Yamaha, Bajaj, Hyundai Mobis, BharatBenz. Enterprise targets; dual role as data source + pilot customer.
- **IndiaMART auto-parts section** — India's largest B2B marketplace, auto parts sub-vertical. Potentially huge training corpus; unknown ToS posture.
- **ONDC buyer apps** — Beckn `/search` protocol as distribution channel (per ADR 011 latent optionality).
- **Regional / vernacular platforms** — Tamil/Telugu/Marathi auto-parts sites once we expand past Hindi belt (Phase 7).

---

## How to use this file

- **Before scraping a new domain:** add a row here with `📋 queued` in scrape-status. Update to `✅ done` when scraped + row count is in `data/raw/MANIFEST.md`.
- **Before reaching out to a prospect:** add a row with `📋 queued` in outreach-status. Update to `🟡 contacted` when DM sent, `✅ pilot signed` when agreement exists, `❌ rejected` otherwise.
- **If ToS or legal concern surfaces:** flag in notes and move to "Dropped / declined" section with reason.

This file lives alongside `context/research/t505-prospects-2026-04-12.md` (point-in-time audit) as the **evergreen, updated-per-session** registry.
