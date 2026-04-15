# Findings — T305 benchmark session (2026-04-15)

Distilled learnings from the round 1 + round 2 benchmark + publication session. These are **patterns**, not just facts — things the next session should know before editing the bench pipeline, training, or making public claims.

---

## 1. Corpus-shape changes the scoreboard by 5-7 pts per model

Same model, same query set — just changing the retrieval corpus (KG 2,121 docs → production 26,835 docs) shifted every model's nDCG@10 down by 5-7 pts. This is not "the catalog is harder" — it's that the joint-pool composition changes, the judge evaluates a different candidate set, and models get penalized for retrieving catalog docs they were never trained on.

**Implication for claims:** Never publish a single-corpus score. Always disclose WHICH corpus. A "v3 beats OpenAI by X%" claim is only meaningful paired with "on corpus Y of size Z." Round 1 (KG-only) and Round 2 (production) must be presented together.

---

## 2. "Production hybrid beats OpenAI" was falsified on this bench

The T402c commit showed "+46% on part_number from BM25 fusion." That number was measured on an internal eval, not joint-pool judged. When reproduced on a joint-pool-graded bench, the hybrid is **net-neutral** vs v3-alone (both ≈ 0.40-0.41 on production corpus).

**Why:** BM25 helps part_number (+5-6 pts) but costs slight regression on other categories (fusion weights not tuned for production data).

**What works:** Re-tuning fusion weights via coordinate descent on dev set pushes hybrid from 0.400 → 0.424 (held-out CV). This was the load-bearing fix.

**Pattern:** Any claim of hybrid improvement must be re-validated against a joint-pool-graded bench over the corpus the claim is being made on. Internal-eval-script numbers are NOT production numbers.

---

## 3. LLM judge — model choice matters (reasoning ≠ better for long pools)

Used `deepseek-reasoner` (DeepSeek R1) first — **failed every query**. Root cause: reasoning model consumes `max_tokens` budget on internal reasoning, leaving zero for JSON output when the pool has >50 candidates.

Switched to `deepseek-chat` (V3 non-reasoning). Worked perfectly. ~22 min for 149 queries over median-60 pools. Cost ~$0.30.

**Pattern:** For graded-relevance judging on long pools (>40 items), prefer non-reasoning models at `temperature=0`. Reasoning quality doesn't help when the task is mechanical ("grade these 60 items 0/1/2").

Also: **bump `max_tokens` to at least 8000** for any judge call handling long pools. R1 needs way more because reasoning tokens count.

---

## 4. Judge-model family bias is a real thing

OpenAI GPT-4o would have been a strong judge — but we were benchmarking OpenAI's embedding model. Using GPT-4o as judge would have subtly favored OpenAI's retrieval because of shared training-data priors (vocabulary, document style). DeepSeek is neutral (none of its family in the bench).

**Pattern:** Never judge an embedding model with an LLM from the same family. For future rounds where we add `embeddinggemma-300m` as a contender, avoid Gemini or PaLM judges. Claude Opus or DeepSeek remain safe.

---

## 5. API rate limits are the #1 operational blocker

Hit unexpected 100K-tokens-per-minute caps on both Cohere (trial) AND Jina (free tier). Without throttling, batch embedding a 26K corpus triggers 429s and fails after retries. With throttling (2s min interval between batches + 65s backoff on 429), both work fine.

Jina was additionally slow per-batch (~20s/batch) — genuine API latency, not rate limit. Not usable for 26K embed at free tier.

**Pattern:** Before launching a full embedding run, test a 3-batch sample to confirm the provider's effective throughput. Budget 10-30 min per provider per 26K-doc run. Test keys work; pagination doesn't tell you about rate limits until you hit them.

See `scripts/_embed_api.py` for the throttled implementations.

---

## 6. Prefix/input_type conventions are LOAD-BEARING for fairness

Six models, six different conventions:
- OpenAI: no prefix
- Cohere: `input_type="search_query"` vs `"search_document"` (asymmetric!)
- Jina: `task="retrieval.query"` vs `"retrieval.passage"`
- e5-large: `"query: X"` vs `"passage: X"` (prefix string, required)
- BGE-m3 dense: no prefix
- v3 (ours): no prefix (inherits BGE-m3)

Getting ANY of these wrong silently drops a model's score 10-30%. A "real" result that comes from misconfigured prefixes is not a result.

**Pattern:** Centralize per-model conventions in ONE table (e.g., `MODELS` dict in `scripts/_embed_api.py`). Sanity-check with a canonical query before the full run. If "brake pad for Swift" → top-1 isn't a brake pad, something is wrong with that model's config.

---

## 7. Joint-pool grading is the only fair way to compare retrieval models

Comparing nDCG across models when each has its own top-20 set → every model looks best on its own preferences. Joint-pool = union of top-20 from all models, grade once, score everyone against same pool = every model judged on the same universe.

**Pattern:** For any multi-model retrieval bench, the gradient is:
- Per-model own-set: cheap, biased, don't trust absolute numbers
- Joint-pool graded: slightly expensive ($0.30 + 30 min), unbiased, defensible

Always use joint-pool for published claims.

---

## 8. Fusion-weight tuning has an overfit gap but a small one (~1 pt)

3-fold CV on 149 queries:
- In-sample tuned nDCG: 0.4313
- Held-out (CV) tuned nDCG: 0.4238
- **Overfit gap: +0.0075 (0.75 pts)**

**Pattern:** Grid-search tuning over 5 classes × 11 values is cheap (~100 evaluations) and the gap is small. Trust the tuned numbers. But always report the CV estimate publicly, not the in-sample number — otherwise a sharp reader will (correctly) call out dev-set-overfit.

---

## 9. Data augmentation is SATURATED at our base-model scale (ADR 015)

Four v4/v5 variants on BGE-m3 + MNR + 11K-ish pairs all landed in the −3% to +2.5% band vs v3. Further augmentation of the same TYPE of pairs hits diminishing returns.

**Pattern:** After reaching saturation on a base model + pair-type combination, ONLY these move the needle:
1. New TYPE of pair (e.g. catalog-style, not KG-Hindi) — what γ proposes
2. New base model (embeddinggemma, gte-multilingual-base) — what γ' proposes
3. Architectural changes (re-ranker on top, Matryoshka truncation, query routing) — strategy 1 in EVAL_REPORT

Don't burn cycles on "one more KG Hinglish pair batch."

---

## 10. Part numbers are a STRUCTURAL miss for embedding models

Every embedding model we tested scores <0.18 on part_number queries (OpenAI = 0.178, v3 = 0.084). Part numbers are arbitrary alphanumeric strings with no semantic content — embeddings cannot cluster them meaningfully.

**Pattern:** Don't try to "fix part_number in the embedding model." It's a BM25 / exact-match / database-filter problem. The production fix is:
- Detect part_number shape at query time (query_classifier already does)
- Route those queries to BM25-heavy or exact-match filter
- Skip the embedding path entirely for pure-PN queries

---

## 11. v3 regresses on Hindi when moved from KG to catalog corpus

Round 1 (KG): v3 Hindi = 0.548 (BEATS OpenAI 0.526).
Round 2 (catalog): v3 Hindi = 0.440 (LOSES to OpenAI 0.544).

Why: v3 was fine-tuned on clean KG-style Hindi pairs ("gaadi ki batti" → battery). Catalog docs have Hindi mixed with English + brand names in ways v3 has never seen.

**Pattern:** A model trained on corpus-style A does not generalize to corpus-style B, even for the same query-class. To fix Hindi-on-catalog: train on Hindi queries paired with catalog-style docs (not KG-style docs).

---

## 12. Publishing numbers BEFORE training protects you from p-hacking

Sequencing δ+ζ+ε (publish) BEFORE γ+γ' (train) locks the target. If we trained first and THEN published, every training tweak would drift toward whatever the dev-149 judge liked this particular run — classic adaptive overfitting. Publishing fixes the public claim; γ+γ' then aims to beat it, with the public forcing honest comparison.

**Pattern:** Always publish the baseline THEN iterate. Never iterate on a private dev set and publish only the final winner.

---

## 13. The real moat is user query logs — which requires prospects

No amount of synthetic pair generation, base-model upgrade, or re-ranker tuning will match 10,000 real prospect queries. OpenAI scale-trained on 100B+ tokens; we'll never match that generically. But on Indian-auto-parts-specific queries, real queries from one prospect's catalog search traffic in 30 days = data OpenAI doesn't have.

**Pattern:** Every prospect demo URL should instrument query logging (`/demo/<slug>` logs every search). The goal of outreach isn't just revenue — it's **annotation-ready data that compounds**. Treat each prospect integration as a data pipeline, not a contract.

---

## 14. "Fair comparison of OUR SYSTEM" ≠ "fair comparison of OUR EMBEDDING"

Two different claims:
- "Our embedding v3 beats OpenAI's embedding" → compare model-vs-model. Round 1 + 2 shows we lose by 4-6 pts.
- "Our SYSTEM beats OpenAI's default retrieval" → compare hybrid stack vs embedding-only. We still lose on this bench, but the gap narrows and per-category wins emerge.

**Pattern:** When writing public copy, be clear which claim you're making. "Our embedding model is #2" and "Our search system is #2" are both defensible; conflating them ("we beat OpenAI") is not.

---

## 15. Honest overfit + limitation disclosure STRENGTHENS credibility

Every limitation (n=149, judge-not-human, fusion tuned on dev, etc.) flagged in EVAL_REPORT makes the claim MORE credible, not less. A CTO reading "tuned via 3-fold CV, in-sample 0.431, held-out 0.424, gap 0.75pts" has a reason to trust us. A claim of "0.431" without context looks p-hacked.

**Pattern:** Publish every caveat. It costs nothing; it buys trust asymmetrically.
