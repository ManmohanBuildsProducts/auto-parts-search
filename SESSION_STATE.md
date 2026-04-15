# Session State

**Rolling dashboard. Open this first.** One page, always current. Claude updates via `/wrap` at session end.

Last updated: 2026-04-15 (Phase 5 live with multi-tenant /demo + auth + /catalog/try dashboard; ready for outreach)

---

## 🟢 Current focus

**Phase 5 has a demoable product.** Public URL via Cloudflare Tunnel serves three shareable surfaces:
- `/catalog/try` — faceted dashboard over our 27K scraped+KG index (for cold outreach clicks)
- `/demo/<slug>/try?key=<k>` — per-prospect scoped demo, concierge-ingested
- `/docs` — Swagger for dev prospects

Concierge flow (`scripts/prepare_demo.py`) handles any input format (CSV/Excel/JSON/JSONL/folder/URL). `/demo` skill + slash command wrap the flow in one Claude Code invocation.

**Live URL right now:** `https://enjoyed-lay-balloon-erik.trycloudflare.com` (ephemeral; dies on Mac reboot / tunnel restart). Named tunnel pending — user owns `whileyousleep.xyz`, will subdomain it when ready.

**Open strategic questions:**
1. Friend flagged: benchmark vs OpenAI text-embedding-3-large + Cohere embed-multilingual-v3 + 25-30 metrics. My honest counter: ~8 categorized metrics beat 30; external bench is T305 (deferred in ADR 015, still valid). Worth executing before LinkedIn post.
2. LinkedIn post draft exists (Angle A build-in-public). Pending user posting + named-tunnel URL swap.

---

## ✅ Done (recent — Phase 5, 2026-04-14/15)

### T402a — Indic tokenizer (commit `6227d4b` + `dac7dda`)
- `auto_parts_search/tokenizer.py` — IndicTokenizer (script detect, normalize, split, bridge lookup, Sarvam fallback, stemmer facade)
- `auto_parts_search/lemma_map.py` — bidirectional Roman↔Devanagari dict, 2,734 R→D + 5,927 D→R entries
- 26 pytest unit tests, 80ms runtime, >1000 tok/s throughput
- 81% of dev queries get cross-script expansion via bridge alone
- Decision (per ADR 010 + research audit): **skip IndicXlit (fairseq broken)**, use Sarvam API as neural fallback

### T402b — Meilisearch BM25 baseline (commit `c5e2c4b`)
- `auto_parts_search/search_bm25.py` — ingest + search wrapper
- 884 KG parts indexed (after HSN-noise filter); MRR 0.297, Recall@5 0.280
- Fixes: `matchingStrategy=frequency` for typo+multi-word; min-word-size 4 for typo tolerance
- BM25 alone is **weaker than v3** but provides complementary signal for fusion

### T402c — Hybrid BM25+v3 RRF + classifier (commit `34fad4b`, **ADR 016**)
- `auto_parts_search/query_classifier.py` — 5-class heuristic classifier (regex + keyword list)
- `auto_parts_search/search_hybrid.py` — RRF (k=60) over BM25 top-30 + v3 embedding top-30
- v3 corpus embeddings precomputed to disk (`data/external/processed/v3_corpus_embeddings.npy`, 8.6 MB)
- Class-specific fusion weights (tuned): part_number 0.8/0.2, symptom 0.1/0.9, brand 0.3/0.7, hindi 0.2/0.8, default 0.5/0.5
- Scorecard vs v3 alone (joint-pool graded on dev-149):
  - Overall graded nDCG@10: **+0.4%** (tie)
  - Recall@5: **+3.2%**
  - **part_number: +46.4%** 🔥 (the real win)
  - brand_as_generic: +3.6%
  - exact_english/hindi/misspelled/symptom: within noise

### T401 — FastAPI /search endpoint (commit `d541cea`)
- `auto_parts_search/api.py` — FastAPI app, CORS, lifespan warm-up
- Endpoints: `/`, `/health`, `/classify`, `/search` (GET+POST), `/stats`
- Warm latency 37-140ms (p50 ~60ms) on local; cold ~8s (sentence-transformers load)
- Pydantic schemas → auto Swagger UI

### T405 — Catalog ingestion (25,952 products, commit `14ddb82`)
- `scripts/ingest_catalog.py` — adds shopify (24,865) + additional (608) + playwright (479) to `parts` index with `doc_type='catalog'`
- Skipped boodmo (1.4M rows, no vehicle specificity)
- Part-number regex extraction from titles (stopword-filtered)
- Index now: 26,835 docs total (884 KG + 25,951 catalog), 48 MB on disk
- **Part-number search now actually works:** `6U7853952` → exact Skoda OEM match

### T409 (partial) — Cloudflare Tunnel deploy (commit `b770395` / tunnel live)
- Ephemeral `https://enjoyed-lay-balloon-erik.trycloudflare.com`
- Free, no account, dies on tunnel restart; named tunnel deferred pending domain decision

### T410 — Multi-tenant /demo/catalog (commit `4174b5f`)
- `auto_parts_search/demo_tenant.py` — upload_catalog + search_in_session + session TTL/LRU eviction
- `POST /demo/catalog` — 10K-SKU single-shot upload
- `GET /demo/{sid}`, `GET /demo/{sid}/search`, `DELETE /demo/{sid}`
- Per-session Meilisearch index `demo_<sid>` + in-memory v3 embeddings
- Closes the gap "we have a search API" → "prospect uploads their catalog, sees their data"

### T411 — Async job flow for large catalogs (commit `ab4339f`)
- `POST /demo/catalog/start` + `batch` + `commit` + `GET /demo/catalog/{jid}`
- Realistic caps: 10K per batch, 500K per job, 500K per URL ingest
- Background thread workers with per-chunk progress callback (65 docs/s on Mac CPU)
- `POST /demo/catalog/ingest-url` — server pulls JSONL from customer URL
- Answers "how do I upload 10 lakh products via API?"

### T412 — Concierge CLI + /try UI + named slugs (commit `1311a27`)
- `scripts/prepare_demo.py` — founder CLI: CSV/XLSX/JSON/JSONL/folder/URL → auto-detect columns → upload → URL
- Pandas+openpyxl-powered parsing; fuzzy column matching; interactive or `--map`
- Named slugs (`/demo/pikpart` not `/demo/d_abc`) via `_sanitize_slug()`
- `auto_parts_search/static/try.html` — vanilla JS prospect-facing search UI with live debounced search, class badges, per-hit meta

### T413 — Guide + skill + slash command (commit `fadf077`)
- `docs/CONCIERGE_DEMO.md` — full playbook
- `scripts/start_all.sh` — idempotent boot (Meili + API + Tunnel)
- `.claude/skills/prospect-demo/SKILL.md` — Claude Code skill that wraps the loop
- `~/.claude/commands/demo.md` — global `/demo` slash command

### T414 — Auth + /catalog/try dashboard (commit `f7c6e6d`)
- Per-session `api_key` (auto `token_urlsafe(16)`) on all new sessions/jobs
- `/demo/{sid}/search` + `/demo/{sid}/try` require `?key=` or `X-API-Key` header (401 otherwise)
- Backward-compat: legacy sessions without keys still work
- `GET /catalog/try` + `GET /catalog/search` — Badho-Search-style public dashboard over the 27K scraped+KG index
- Facets (brand / vehicle_make / source / doc_type) from Meilisearch `facetDistribution`
- Per-stage timing breakdown (classify / embed / bm25 / fuse)

---

## 🟡 In progress / partial

- **Domain decision** — user owns `whileyousleep.xyz`. Subdomain `search.whileyousleep.xyz` recommended ($0, 15 min). Alternative: `.in` on Cloudflare Registrar (~$6/yr). Named tunnel setup deferred until decision.
- **LinkedIn post** — draft ready (3 angles: build-in-public, technical, problem-pitch). Waiting for named-tunnel URL before posting, and for user to take dashboard screenshots.

---

## 🔴 Blocked / pending external action

- **Outreach to Pikpart / AutoDukan / Parts Big Boss** — demo infra ready; user action on own pace.
- **T305 external benchmark** (see open question #1 below) — requires OpenAI + Cohere API keys + ~$2 spend.
- **IndicVoices gated dataset** — access request pending at HF Hub (not critical; deferred indefinitely).

---

## 🔷 Next up (ranked by leverage)

1. **T305 — external embedding benchmark** — Friend's feedback: compare v3 vs OpenAI text-embedding-3-large + Cohere embed-multilingual-v3 + jina-v3 + multilingual-e5-large on joint-pool graded dev set. Cost ~$2, time ~2 hr. Honest counter on "25-30 metrics": 8-10 metrics suffice (graded nDCG@10, Recall@5, per-6-type breakdown, latency, p95, cost-per-1K); 30 metrics is noise. See open question below for the metric list I'd propose.
2. **Named Cloudflare tunnel on `search.whileyousleep.xyz`** — 15 min, $0. Permanent URL for LinkedIn + outreach.
3. **LinkedIn post** — Angle A draft is ready in chat; swap URL + screenshots + post.
4. **T506 — free audits for Pikpart / AutoDukan / Parts Big Boss** — unchanged; highest-EV external action.
5. **Hetzner deploy** — €3.29/mo, ~3 hr. When first prospect says "show me": so Mac can sleep.
6. **Session listing admin UI** — ~30 min. `/demo` lists active sessions with their URLs.
7. **Shopify one-click connector** — ~1 hr. Paste Shopify store URL, auto-fetch /products.json.
8. **Named tunnel + API key auth on /catalog/try** — ~30 min. Prevents random public abuse once URL is in a LinkedIn post.

---

## 🗝 Key recent decisions

- **ADR 016: Hybrid BM25+v3 RRF is production** — class-weighted (part_number BM25-dominant, symptom embedding-dominant). +46% on part_number; +3% Recall@5 overall.
- **Concierge-first product model** — prospects won't integrate DB credentials on a demo URL. Founder ingests their catalog manually via `scripts/prepare_demo.py`; prospect gets a clean `/try` URL with their data. Multi-tenancy (DB connectors, API vault) deferred to first paid pilot.
- **Per-session API key auth** — every new `/demo` session generates a key; URL requires `?key=<k>` or `X-API-Key` header. Legacy sessions work without. Key printed by CLI.
- **No IndicXlit, use Sarvam API fallback** — IndicXlit depends on broken fairseq wheels; Sarvam Transliterate API gives same quality via HTTP at ₹19/10K chars.
- **Skip boodmo (1.4M rows)** from catalog ingestion — no vehicle specificity, drowns index recall.
- **HSN-concat names filtered at ingest** — 1,237 dropped, leaving 884 clean KG part docs.
- **Cloudflare Tunnel > ngrok** — no visitor interstitial, unlimited throughput on free tier.

---

## 🚨 Watch-outs (surface every session)

- "Done" ≠ "artifact exists." Done = verified outcome.
- **Tunnel URL is ephemeral** — `https://enjoyed-lay-balloon-erik.trycloudflare.com` dies on restart. Named tunnel is the fix; domain decision open.
- **Mac must stay awake** for demos. `caffeinate -d -i &` or deploy to Hetzner.
- **Never trade quality silently** (memory/feedback_never_trade_quality_silently.md) — all lr/batch/seq/epoch/loss decisions require explicit user approval before changes.
- **Co-occurrence ≠ synonymy** (memory/learnings.md) — mistaking this in v1.0 caused catastrophic regression.
- **Sarvam API key + DeepSeek API key are in `.env`** (gitignored). Rotate when exposed in chat.
- `TASKS.md` is the single task-board source.
- **26 tokenizer unit tests must stay green** on every pre-push.

---

## Live infrastructure

| Service | Where | Status | Access |
|---|---|---|---|
| Meilisearch 1.42 | local `127.0.0.1:7700` | running | `curl 127.0.0.1:7700/health` |
| FastAPI | local `127.0.0.1:8000` | running | `curl 127.0.0.1:8000/health` |
| Cloudflare Tunnel | ephemeral public URL | running | `grep trycloudflare /tmp/cf/tunnel.log` |
| HF model repo | `ManmohanBuildsProducts/auto-parts-search-v3` (private) | shipped | — |
| HF pair sets | `auto-parts-search-pairs-{v4a,v4b,v4c,v5}` | shipped | — |
| HF raw snapshot | `ManmohanBuildsProducts/auto-parts-search-raw` | shipped | — |

Bootstrap after Mac reboot: `bash scripts/start_all.sh`

---

## How to use this file

- **You (passenger) opening project:** read this. 30 seconds.
- **Claude starting a session:** auto-injected via `~/.claude/hooks/session-state.sh`. Verified wired as of 2026-04-15.
- **Claude ending a session:** `/wrap` — updates this file + proposes commits.
