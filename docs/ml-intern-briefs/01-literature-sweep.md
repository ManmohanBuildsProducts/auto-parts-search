I'm building a domain-adaptive embedding model for Indian auto-parts search.
Queries are in Hindi, Hinglish (code-switched), or Roman-transliterated Devanagari.
Documents are English-dominant catalog product titles (e.g. "Maruti Swift Rear Brake Pad - ATE OEM").

**Current model:** BGE-m3 fine-tuned with MultipleNegativesRanking loss (sentence-transformers).
**Training data:** ~27K pairs from a domain knowledge graph (HSN taxonomy, ITI diagnostic
chains, vehicle compatibility from NHTSA). Data augmentation (YouTube Hindi, Aksharantar
transliteration, Hinglish bridge pairs) has been tried — all 4 variants saturated in the
[-6.8%, +2.4%] band vs v3 on our graded eval set.

**Benchmark:** 149-query graded dev set (Hindi, Hinglish, brand-as-generic, symptom,
part-number, misspelled). Evaluated via nDCG@10 on a joint-pool (top-20 from 6 models,
graded by DeepSeek V3 judge). Production corpus: 26,835 catalog docs.

**Current scores (nDCG@10, production corpus):**
- Our v3:                         0.430
- OpenAI text-embedding-3-large:  0.468  ← target to beat

**Per-category gaps (v3 vs OpenAI):**
- Hindi/Hinglish queries:   v3 0.440 vs OpenAI 0.544  (-10 pts)
- brand_as_generic queries: v3 0.320 vs OpenAI 0.470  (-15 pts)
- part_number queries:      v3 0.084 vs OpenAI 0.178  (-9 pts, routing to BM25 handles this)
- symptom queries:          v3 0.390 vs OpenAI 0.450  (-6 pts)

**What has been tried and FAILED:**
- 4 data augmentation variants (YouTube Hindi captions, Aksharantar transliteration,
  Hinglish bridge pairs): all landed in [-6.8%, +2.4%] band. Data augmentation on
  BGE-m3 is saturated — more pairs of the same type don't help.
- Pair quality is high (graded labels, MNR loss); the type of pairs is the bottleneck.

**What I need:**
1. Survey arxiv + HF Papers for techniques specifically targeting:
   (a) Catalog-aware embedding fine-tuning for product search (not general NLP benchmarks)
   (b) Cross-lingual / code-switched embedding alignment (Hindi-English mixture)
   (c) Brand-generic disambiguation in dense retrieval
   (d) Reranker distillation from an LLM judge for domain-specific retrieval
2. Walk citation graphs — don't stop at top-level survey papers. Find the
   implementation papers that show training recipes + ablations + training data strategies.
3. Suggest the TOP 3 techniques worth implementing, ranked by:
   - Expected nDCG@10 gain on the Hindi + brand_as_generic slices
   - Data requirements (we have 26K catalog docs and a 149-query graded eval set)
   - Feasibility on A100 (1-2 hr training run max)
4. For each technique: provide the key paper citations, a sketch of the training
   data format required, and an estimate of gain range based on paper results.

**Hard constraints:**
- No distillation from OpenAI outputs (commercial ToS violation).
- Claude (Anthropic) distillation is explicitly allowed.
- Must handle Devanagari + Roman script queries against English-dominant catalog docs.
- No new base model exploration needed right now — focus on training data strategies
  and reranker architectures on top of BGE-m3.
