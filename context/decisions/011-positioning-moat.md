# Decision 011: Positioning — vertical now, horizontal is earned, not pivoted to

**Date**: 2026-04-12
**Status**: Decided
**Supporting research**: `context/research/market-audit-2026-04-12.md`

## Context
Considered a pivot from "Indian auto parts search" to "horizontal search platform for mid-market e-commerce." The market audit (2026-04-12) returned three findings that decide the question:

1. **Algolia has zero Hindi NLP.** Community forum thread from 2018 is the only Indic-language mention; the documented supported-languages list excludes Hindi. NeuralSearch (launched 2023) has no Indian customer case study. Algolia has a Bangalore engineering office and has still made no public commitment. This is the single largest unexploited gap in the category.
2. **Klevu's #1 low-star complaint is cost**, not retrieval quality. Floor is ~$499/mo with undocumented scaling charges. A cheaper domain-specific alternative has a demand-validated opening at the Indian mid-market price point (Rs.8–25K/mo).
3. **Constructor grows via enterprise ACV ($100K+).** It's not competing for Indian mid-market, and cannot without a complete repricing.
4. **No Indian commerce platform is publicly named as a customer of any Western search vendor.** Koovers (now Schaeffler India, 508 employees), SparesHub, Autozilla, Nykaa, Myntra, Meesho — all building in-house or on Elasticsearch defaults.
5. **ONDC is the structural distribution unlock** — 10M+ transactions/month, open Beckn `/search` protocol, no semantic/Hindi intelligence layer. Any buyer app can integrate a third-party query-intelligence service.

## Decision

### Stay vertical. Build auto parts deeply first.
Going horizontal today means competing with Algolia, Constructor, and Athos Commerce (Klevu+Searchspring, $PSG-backed) on their turf — distribution, integrations, 10-year head starts. Solo founder, part-time, cannot win that war.

### Reposition the public framing
From: "Search API for Indian auto parts."
To: **"Commerce search for Indian multilingual markets — auto parts first."**

Same code, same current roadmap. Preserves platform optionality without committing to it. Opens the door to a second vertical (building materials, pharma, electronics) once the first is shipping.

### The moat is the feedback loop, not the model
In descending order of defensibility for a solo founder:
1. **Compounding query→click→retrain loop** — Algolia's real moat. Zero defensibility until ≥1 live customer is producing query logs. This is why GTM-before-model urgency is real.
2. **Vertical workflow lock-in** — integrated into checkout/PDP. Kicks in at customer #2–3.
3. **Brand in a niche** — "the Hindi commerce search people." Content + partnerships.
4. **Proprietary Indic data** (KG + Hindi/Hinglish pairs) — transient moat, depreciates ~30%/6mo as base models improve. Funds 1–3.

"Better fine-tuned model" is not the moat. "Better-than-Algolia in Hindi by 6 months" is the wedge. "First to close the feedback loop with Indian commerce platforms" is the moat.

### ONDC as latent optionality
Do not build for ONDC now. Do track the Beckn `/search` protocol. When we have 2 paying customers from non-ONDC channels, evaluate whether to ship an ONDC buyer-app plugin as the distribution multiplier.

### GTM sequencing fix
Previous roadmap blocked T505 (identify prospects) and T506 (free audit) behind T402 (hybrid search). This is backwards. **A free search audit does not need a deployed product** — a Jupyter notebook with OpenAI `text-embedding-3-large` + the prospect's CSV + their top queries is sufficient. Move T505/T506 forward. Ship first audit within 2 weeks of Phase 2b cleanup completing.

## Consequences
- No pivot to horizontal platform in 2026.
- Public-facing copy updates: "auto parts" → "Indian multilingual commerce search; auto parts is our beachhead."
- Second-vertical test is scheduled during Phase 5 (one non-auto-parts pilot before claiming "platform"). If transfer ≥70%, platform thesis is validated with evidence; if <40%, vertical is the ceiling and we stay.
- GTM work (T505/T506) is unblocked from technical dependencies. A notebook-based audit is the MVP wedge, not a deployed API.
