# auto-parts-search

**A domain-specific search stack for Indian auto parts** — Hindi/Hinglish queries, noisy misspellings, symptom-to-part lookups, and part-number cross-refs, over a 26K-SKU catalog built from scratch.

Solo-built, part-time. Active development since Feb 2026.

---

## Why this exists

Generic search (Elastic, OpenAI embeddings, Cohere multilingual) falls off a cliff on Indian auto parts queries:

- **Script-mixed input**: `"brek pad activa"`, `"ब्रेक पैड"`, `"bumper scorpio 2015"`
- **Brand-as-generic**: `"bosch"` means "spark plug" to half the market
- **Symptom queries**: `"gaadi se dhuan aa raha hai"` → exhaust / piston ring / valve seal
- **Part-number jungle**: OEM numbers, aftermarket cross-refs, supersessions
- **Transliteration drift**: `engine ↔ injun ↔ इंजन ↔ enjin`

None of the off-the-shelf options handle all five at once. So the plan is: build a vertical index with a custom tokenizer, a knowledge-graph backbone, and a fine-tuned embedding layer — and benchmark ruthlessly against the generalists.

---

## What works today

| Capability | Status | Numbers |
|---|---|---|
| Catalog index (Meilisearch + v3 embeddings) | ✅ live | **26,835 SKUs** (25,951 scraped + 884 KG-enriched), 48 MB on disk |
| Indic tokenizer (script detect, normalize, bridge lookup, Sarvam fallback) | ✅ live | 2,734 Roman→Devanagari + 5,927 reverse entries; 81% of dev queries get cross-script expansion |
| Hybrid retrieval (BM25 ⊕ v3 via RRF, class-weighted fusion) | ✅ live | **part-number recall +46.4%** vs v3 alone on dev-149 joint-pool eval |
| 195-query evaluation benchmark (6 query types) | ✅ live | exact_english / hindi / misspelled / symptom / brand_as_generic / part_number |
| FastAPI `/search` + multi-tenant `/demo/<sid>` (prospects upload their catalog, query it live) | ✅ live | Cold ~8s, warm p50 ~60ms; 500K-SKU async ingest |
| Knowledge graph (HSN + NHTSA + ITI + ASDC) | 🟡 v1 hand-curated, v2 LLM re-extraction planned | 884 KG parts after HSN-noise filter |
| Domain-specific embedding fine-tune (v3 → v4+) | 🟡 Phase 3b reopened | catalog-aware gap being closed |
| Named-tunnel public demo on `whileyousleep.xyz` | ⏭️ next | currently on ephemeral Cloudflare Tunnel |

The **+46.4% part-number recall** is the headline result — real OEM lookups like `6U7853952` now return the right Skoda part, where v3-alone missed.

---

## Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │                 Query                        │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                 ┌─────────────────────────────────────────────┐
                 │  IndicTokenizer                              │
                 │  script-detect → normalize → split →         │
                 │  bridge lookup (Roman↔Devanagari) →          │
                 │  Sarvam neural fallback → stemmer facade     │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                 ┌─────────────────────────────────────────────┐
                 │  Query classifier (5-class regex+keyword)    │
                 │  → part_number / symptom / brand / hindi /   │
                 │    default  →  picks fusion weights          │
                 └──────────────────────┬──────────────────────┘
                                        ▼
             ┌──────────────────────────┴───────────────────────────┐
             ▼                                                       ▼
   ┌───────────────────┐                                 ┌───────────────────────┐
   │ BM25 (Meilisearch)│                                 │ v3 embeddings         │
   │ frequency-match,  │                                 │ (sentence-transformers│
   │ typo-tolerant     │                                 │  multilingual, 8.6 MB │
   │                   │                                 │  corpus cached)       │
   └─────────┬─────────┘                                 └───────────┬───────────┘
             │                                                        │
             └──────────────────┬─────────────────────────────────────┘
                                ▼
                 ┌─────────────────────────────────────────────┐
                 │  RRF fusion (k=60), class-weighted           │
                 │  part_number 0.8/0.2  •  symptom 0.1/0.9     │
                 │  brand 0.3/0.7        •  hindi 0.2/0.8       │
                 └──────────────────────┬──────────────────────┘
                                        ▼
                                   top-K results
```

Stack: Python 3.11+, `sentence-transformers`, Meilisearch, FastAPI, Playwright (for Angular/Magento scrapes), Shopify `products.json` (for Shopify catalogs), SQLite (knowledge graph), Cloudflare Tunnel (demo exposure).

---

## Running it

```bash
# Install
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium   # for SPA scrapers

# Pipeline
python3 -m auto_parts_search scrape           # Shopify + Playwright scrapers
python3 -m auto_parts_search pairs            # Generate training pairs
python3 -m auto_parts_search benchmark        # 195-query eval set
python3 -m auto_parts_search build-graph-db   # Materialize SQLite KG (ADR 007)
python3 -m auto_parts_search stats

# Serve
uvicorn auto_parts_search.api:app --reload
# → http://localhost:8000/docs for Swagger

# Tests
python3 -m pytest tests/ -v
```

See `context/ROADMAP.md` for the six-phase plan and `SESSION_STATE.md` for the current-week snapshot.

---

## Project discipline

This repo deliberately over-invests in decision hygiene because solo, part-time work rots fast without it:

- **17 ADRs** under `context/decisions/` — every architectural + strategic call, numbered, never silently edited.
- **`SESSION_STATE.md`** — one-page rolling dashboard, updated every session.
- **`TASKS.md`** — single source of truth (no parallel Kanban).
- **`memory/regressions.md`** — incidents + patterns to avoid.
- **`memory/findings.md`** — distilled learnings on evaluation design (judge choice, rate limits, tuning overfit, what actually moves the needle).
- **Golden training set is immutable** — experiments branch into `data/training/experiments/<date>-<hypothesis>/`; promotion to `golden/` is a deliberate commit.
- **Reproducibility**: every generator uses `random.seed(RANDOM_SEED)` + manifest (ADR 009).
- **No open-loop pair generation** — every new pair set trains + benchmarks a model (ADR 006).

Built with Claude Code as the primary collaborator, with an explicit `/shaping → /brainstorm → /plan → /build → /review → /ship` workflow.

---

## Status

**Phase 1 (Training dataset)** — ✅ done
**Phase 2 (Knowledge graph)** — ✅ v1 live, v2 LLM re-extraction planned
**Phase 3 (Embedding fine-tune)** — ✅ v3 shipped, 🟡 Phase 3b reopened for catalog gap (ADR 017)
**Phase 4 (Hybrid retrieval)** — ✅ live (ADR 016)
**Phase 5 (Search API + multi-tenant demo)** — ✅ live on ephemeral tunnel
**Phase 6 (GTM + first customer)** — ⏭️ in progress

Open to collaborators and feedback, especially anyone who's shipped vertical search at scale.

---

## License

Source code: MIT.
Training data (`data/training/golden/*`, `data/external/processed/*`) and the 195-query benchmark are released for research use; please cite this repo if you build on them.
