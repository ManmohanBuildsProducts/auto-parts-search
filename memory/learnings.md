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

## Training / Embeddings

- **Co-occurrence is not synonymy.** First v1 fine-tune of BGE-m3 regressed 10.6% below the base on dev MRR (0.343 vs 0.384) — misspelling zero-rate went 0% → 26%, exact-English 0% → 18%. Root cause: 2,389 graph-derived co-occurrence pairs ("parts sharing a system" / "parts sharing a root-cause symptom") were labeled 1.0 in training data. MNR loss then taught the model that "12V Auxiliary Battery" ≡ "BMS" because they co-occur in the EV system. Fix: co-occurrence → label 0.5 (related, not synonymous). Membership (part ↔ system) and symptom_part (symptom ↔ part) stay at 1.0 — those *are* same-intent signals. Lesson: when writing pair generators, the *semantics* of label=1.0 is "interchangeable in a query" — audit every pair source against that bar.
- **MNR loss is unforgiving with polluted positives.** Because MultipleNegativesRanking pushes *every other batch item* away from each anchor, a few thousand mislabeled positives can wipe out the base model's pre-training. ~18% noise in the positive set was enough for catastrophic forgetting of general-purpose retrieval in one epoch.
- **The Phase 3 gate discipline paid off.** Plan said "if v1 doesn't beat base by ≥10% on dev, stop — don't tune hyperparameters, fix the data." Doing exactly that caught a structural bug we'd have missed while chasing lr/batch/warmup. Cost: one Colab run (~$0) + 30 min. Keep this guardrail on every future training iteration.
- **e5 family needs `query:` / `passage:` prefixes.** Without them, multilingual-e5-large scored MRR 0.30 on the 195-query benchmark; with them it jumped to 0.39. Always check a model card for required prompt formats before drawing conclusions.
- **Jina v3 install is broken on Mac CPU.** Its custom sentence-transformers module depends on `xlm-roberta-flash-implementation` which ships a broken `xlm_padding.py`. Not worth the debug time on Apple Silicon; try a cloud GPU or substitute BGE-m3 if you need a Jina comparison.
- **BGE-m3 + T4 memory budget.** Fine-tuning BGE-m3 (568M params) on a 15GB T4 requires batch ≤16 + max_seq_length ≤128 + fp16 AMP (`use_amp=True`). Batch 32 / seq 256 OOMs at step ~24/405. fp16 roughly halves peak memory with no observed quality regression.
- **Gradient checkpointing recovers +50% batch on memory-tight GPUs.** Colab Free T4 varies 14.5-15.0 GB by host. Adding `model[0].auto_model.gradient_checkpointing_enable()` trades ~25% backward-pass compute for ~30% VRAM reduction; gradients identical so zero quality impact. Let v4 ablation survive batch 32 on 14.5 GB T4 when plain fp16+batch 32 OOMed.
- **IndicXlit depends on broken fairseq wheels.** The `ai4bharat-transliteration` pip package transitively requires `fairseq` which has no installable wheel as of 2026-04. Gave up after failing 2+ install paths. Pivot: use Sarvam Transliterate API via HTTP for neural fallback — works cleanly, ~100-200ms latency, ₹19/10K chars. For static bridge coverage (~95% of domain queries), Aksharantar curated pairs + our KG Hinglish bridge are sufficient; Sarvam only fires on bridge-misses.

## Phase 5: Search system + product packaging

- **Meilisearch `matchingStrategy=frequency` beats `last` for typo+multi-word.** With `last` (default), "brek pad" returns 0 hits because Meilisearch requires both terms to match before dropping. `frequency` drops the least-frequent term first, letting typo tolerance fire on the remaining word. Switched all /search calls to `frequency`.
- **Meilisearch typo tolerance min-word-size defaults (5/9) miss common short misspellings.** Lowered to 4/7 so "brek" (4 chars) gets 1-typo tolerance to catch "brake". No false-positive harm observed on 100-query spot check.
- **Meilisearch has NO Devanagari tokenizer.** Charabia (their tokenizer lib) pipelines CJK, Thai, Hebrew, and Latin — Devanagari falls through to whitespace split, which breaks on virama-joined compounds. **Must pre-tokenize Devanagari catalog text before indexing.** We do this in `IndicTokenizer.index_tokens()` via `indic-nlp-library` normalize + split.
- **BM25 alone is weaker than fine-tuned embedding at every category**, even after tokenizer fixes. MRR 0.297 vs v3's 0.484 on dev-149 binary. But BM25 provides complementary signal: **hybrid RRF +46% on part_number** (embeddings can't match OEM alphanumeric strings). Don't choose between BM25 and embedding; fuse them.
- **Reciprocal Rank Fusion (RRF) is the right default fusion.** Parameter-free (k=60 is stable), works with partial overlap, no training needed. Tried weighted linear fusion; RRF with class-specific weights (part_number → BM25-heavy, symptom → embedding-heavy) cleanly beat it.
- **Query-class routing matters more than the fusion algorithm.** Tuning fusion weights per class — `(0.8, 0.2)` for part_number vs `(0.1, 0.9)` for symptom — recovered a 5% regression on symptom queries that the default `(0.5, 0.5)` fusion introduced. A lightweight regex classifier (no model) handles this in <1ms.
- **LLM-generated transliterations as training positives = noise.** v4c added 2,614 DeepSeek-generated Hinglish-bridge pairs and regressed 2.7% vs v4b. Same pairs are fine as a *retrieval-time bridge dict* (where noise averages out over query→candidate matching) but toxic as *training positives* (where MNR loss treats every pair as a must-preserve synonym).
- **Query-ification helps symptom (+14%) but costs misspelled (−21%).** Training on LLM-rewritten mechanic-speech-as-user-queries shifts the model's distribution: it gets better at natural phrasing but loses tolerance for raw typos. Zero-sum at our data scale; ship v3, fix misspellings via BM25 hybrid instead of chasing embedding.
- **Scrape boodmo.com at your peril.** 1.4M sitemap URLs but zero vehicle specificity and zero brand — indexing it drowns the signal from curated sources. Excluded from the catalog ingest; kept SparesHub/BikeSpares/eAuto (25K docs with real OEM part numbers in titles).
- **HSN concat-taxonomy "part" names poison search.** 1,237 of 2,121 KG parts had HSN-hierarchy names like `Parts...:Suspension systems and parts thereof:*For the industrial assembly of ...`. Filtered at ingest (`len(name) > 80 or ":" in name`) leaves 884 clean docs. Ranks improve dramatically; no real parts dropped.
- **Sarvam-M LLM is a reasoning model with a 2048-token starter-tier cap.** Sarvam's chat API defaults to reasoning mode (`<think>...</think>` eats tokens) and the starter tier caps `max_tokens` at 2048. Burned 30 min fighting it as a judge model before switching to sarvam-105b (128k context) which worked. Lesson: check the model's reasoning-mode behavior before using for structured JSON output.
- **Cloudflare Tunnel > ngrok free for demo URLs.** ngrok free tier shows a warning interstitial to visitors (kills demo vibes) + caps at 40 req/min + 4 concurrent conns. Cloudflare quick-tunnel gives clean HTTPS, no interstitial, unlimited rate. Tradeoff: URL changes per tunnel restart (fix: named tunnel with a free Cloudflare-DNS'd domain).
- **For demos, concierge beats self-serve.** Prospects won't paste DB credentials into a demo URL they've never heard of — but they'll email a CSV. Founder takes the file, runs a CLI, sends back a scoped `/try` URL with the prospect's data. `scripts/prepare_demo.py` auto-detects columns (pandas fuzzy match), uploads via API, prints the shareable URL. Self-serve upload UI is Tier 3; concierge is Tier 1 for first 5 demos.
- **Meilisearch requires explicit `filterableAttributes` for facets.** Attributes that appear in `filter=` queries or `facets=` must be pre-declared. We initially missed `doc_type` and `source`; faceted filtering 400'd until we PATCHed the settings.

## Phase 3b: Training signal & architecture (2026-04-22, from ml-intern literature sweep)

- **Standard InfoNCE/MNRL actively degrades pre-trained embedders past the saturation point.** Tamber et al. (CADeT, arxiv:2505.19274 + 2502.19712) show that for strong pre-trained bi-encoders like BGE-m3, more contrastive pairs of the same type past a threshold *hurt* rather than help. This is the root cause of v4a/b/c/v5 all failing the gate — it wasn't data volume or quality, it was the wrong loss paradigm. Fix: switch to **cross-encoder listwise distillation** where the training signal is soft rankings from a teacher, not binary/graded contrastive pairs.

- **Listwise distillation recipe:** Generate 6 query types per catalog passage (Hindi natural, Hinglish natural, Romanized Devanagari, English technical, symptom/description, brand+generic variant). Score top-20 candidates with a cross-encoder teacher (bge-reranker-v2-m3). Train bi-encoder to minimise KL(student rankings ‖ teacher rankings) + InfoNCE (λ=0.6/0.4). Filter: keep only queries where retriever returns gold in top-20 AND teacher ranks gold #1. Yields ~30-50K training queries from 26K catalog. Expected gain: +4 to +8 nDCG@10 overall; +6 to +12 Hindi/Hinglish.

- **CLEAR cross-lingual alignment (arxiv:2604.05684, 2604.05821):** BGE-m3's English bias in mixed-language pools explains the Hindi-on-catalog regression (v3 0.440 vs OpenAI 0.544). Fix: reversed contrastive loss — use passage as anchor, Hindi/Hinglish queries as positives/negatives — plus KL(S_en ‖ S_hi) distribution alignment. Transliteration pairs (Devanagari ↔ Roman) as additional positives. Training data: translate existing 27K English pairs to Hindi/Hinglish via NLLB-200 or Claude. Can stack on top of listwise distillation. Expected gain: +5 to +10 on Hindi slice.

- **EBRM entity-aware pooling (arxiv:2307.00370):** brand_as_generic -15pt gap is because the model collapses brand and generic semantics. Fix: entity-aware mean-pooling over BRAND/PART_TYPE/MODEL spans + entity-weighted InfoNCE (upweight brand/part-type contrasts 2-3×). Our KG already has this entity taxonomy — HSN codes give PART_TYPE, ITI gives SYMPTOM, scrapers give BRAND. Expected gain: +8 to +15 on brand_as_generic slice.

- **All 5 ml-intern-cited papers verified on arxiv (2026-04-22).** arxiv IDs 2604.05684, 2604.05821, 2505.19274, 2502.19712, 2409.17326 all exist with matching titles. The "2604.xxxxx" IDs are April 2026 papers — very fresh; the research direction is current.

- **Recommended implementation order:** Technique 1 (listwise distillation) → Technique 2 (CLEAR alignment, reuses parallel data from T1) → Technique 3 (EBRM entity-aware, can be fused at inference). Combined estimated gain: 0.430 → 0.485-0.520 nDCG@10, beating OpenAI 0.468.

## Phase 3b engineering-discipline mistakes (2026-04-22, T610 execution)

Four operational regressions burned a session of cleanup during CADeT listwise execution: (A) `pip install -U` on a shared ML dep broke transformers, (B) top-level heavy imports crashed tests at collection, (C) scripts worked as `-m` but not direct, (D) `model.encode()` returns no-grad tensors and silently breaks training loops. Full post-mortem in `memory/regressions.md` § "T610 / CADeT execution". Pre-flight checklist for any new ML-engineering plan: pin HF versions in requirements.txt at bootstrap, lazy-import `transformers`/`torch` inside functions, add sys.path fallback to scripts, never call `.encode()` inside training — use `model(features)` directly.
