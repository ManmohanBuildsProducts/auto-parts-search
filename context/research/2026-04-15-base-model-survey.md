# Base-Model Survey — candidates to replace BGE-m3 for v4 fine-tune

**Date:** 2026-04-15
**Context:** Round-2 bench (26K corpus) showed v3+BM25-hybrid (0.430 nDCG@10) trailing OpenAI `text-embedding-3-large` (0.468), especially on Hindi (−10pt), brand_as_generic (−15pt), and part_number (−9pt). ADR 015 paragraph "when to revisit" explicitly allows a new-base-model option; this survey identifies the strongest free, commercially licensed multilingual embedding base that could plausibly beat BGE-m3 on our workload.

**Constraints:**
- Commercial use allowed (we ship a paid API).
- Multilingual, Hindi required.
- Size ≤ ~600M parameters (BGE-m3 is 568M; Colab T4 fine-tune budget).
- Released after Feb 2024 (the BGE-m3 baseline).

---

## Candidates assessed

| # | Model | Params | Released | License | Hindi? | Fine-tune tooling |
|---|---|---|---|---|---|---|
| 1 | `google/embeddinggemma-300m` | 308M | Sep 2025 | Gemma Terms (commercial allowed with conditions) | ✅ 100+ langs, trained on Hindi | Sentence-Transformers supported |
| 2 | `Alibaba-NLP/gte-multilingual-base` | 305M | Feb/Jul 2024 | **Apache-2.0** | ✅ 70+ langs incl. Hindi | Sentence-Transformers; requires `trust_remote_code=True` |
| 3 | `nomic-ai/nomic-embed-text-v2-moe` | 475M total / 305M active (MoE) | Feb 2025 | **Apache-2.0** | ✅ 100+ langs incl. Hindi | Sentence-Transformers; MoE routing complication |
| 4 | `jinaai/jina-embeddings-v3` | 570M | Sep 2024 | **CC-BY-NC-4.0** | ✅ Hindi in 30 "best-supported" | ST supported |
| 5 | `BAAI/bge-m3-unsupervised` / later BGE | 568M | Feb 2024 | MIT | ✅ 100+ langs | ST |
| 6 | `nvidia/NV-Embed-v2` | ~7B (Mistral-based) | 2024 | CC-BY-NC (non-commercial) | partial | heavy |
| 7 | `sarvamai/sarvam-1` (LM, not embedding) | 2B | 2024 | Open weights, commercial | ✅ 10 Indic langs incl. Hindi | — (not an embedding model; skip) |

### Eliminated

- **NV-Embed-v2:** ~7B params — Colab T4 fine-tune is impractical; license is non-commercial anyway. SKIP.
- **jina-embeddings-v3:** license is **CC-BY-NC-4.0**. Commercial use requires a separate paid license from Jina. For a pre-revenue founder project this is a hidden cost trap; **disqualified on license**.
- **Sarvam-1:** a 2B generative LM, not an embedding model. Would require training an embedding head from scratch. Out of scope.
- **bge-m3-unsupervised:** same base family and era as our current v3 — won't move the needle. BAAI's newer releases (`bge-multilingual-gemma2`, `bge-vl`) are either multimodal or 9B+; neither is a better drop-in replacement. SKIP.

### Shortlist (viable)

1. **`google/embeddinggemma-300m`** (Sep 2025)
2. **`Alibaba-NLP/gte-multilingual-base`** (Feb 2024 — at boundary of "after BGE-m3")
3. **`nomic-ai/nomic-embed-text-v2-moe`** (Feb 2025)

---

## Detailed evaluation

### 1. EmbeddingGemma-300m (TOP PICK)

**Architecture:** Gemma-3 encoder, mean-pooling, 768-dim output, 2K context. Matryoshka Representation Learning (MRL) → can truncate to 128/256/512 dim at serve time (useful for Meilisearch vector index size).

**Numbers (claimed):**
- "State-of-the-art MTEB results among models <500M params" (per Google DeepMind blog, Sep 2025).
- "Strongest per-language result on cross-lingual retrieval among sub-500M models" — includes the 100+ training languages, Hindi included.
- Comparable to models "double its size" (implicitly: comparable to BGE-m3 at 568M).
- **Specific MIRACL-Hindi number not published** in survey sources — this is a gap we need to benchmark ourselves before committing.

**Size:** 308M — 45% smaller than BGE-m3. Fine-tune on T4 is much faster; inference in production roughly 2× throughput.

**License:** Gemma Terms of Use — commercial use permitted, but ships with a "prohibited uses" clause and requires passing-through of restrictions to downstream users. Practical impact for our API: **we can ship**, but must include the Gemma notice. Less permissive than Apache-2.0 but workable.

**Risks:**
- License friction if we ever resell model weights (we don't currently plan to).
- Unpublished Hindi-specific retrieval numbers; has to be benchmarked on our dev-149 before fine-tuning.
- 2K context is shorter than BGE-m3's 8K — irrelevant for our short-query use case.

**Rationale for top:** Best size/quality trade-off, newest architecture (Gemma-3 backbone is stronger than XLMRoberta that BGE-m3 uses), MRL out of the box helps our vector-index ops cost, and Google has strong infra for multilingual training data (including Indic). Worth the modest license friction.

### 2. gte-multilingual-base

**Architecture:** NewModel backbone (dense + sparse output heads), 305M params, 8K context, 70+ languages.

**Numbers:** Alibaba's release claims competitive MIRACL scores; community benchmarks on MMTEB place it among the top 300M-class multilingual models. **No published MIRACL-Hindi head-to-head vs BGE-m3** in the sources I reviewed.

**License:** **Apache-2.0** — most permissive of the shortlist. No pass-through or notice requirement.

**Risks:**
- Published Feb 2024 (same era as BGE-m3); may share data-ceiling characteristics. Newer is usually better, and we're adding 1.5 years of lag by picking this vs EmbeddingGemma.
- Requires `trust_remote_code=True` (minor operational concern on hosted inference).
- Similar size to BGE-m3 — doesn't get us the inference-cost win.

**Rationale for runner-up:** License is the best-in-class, and it's the conservative choice if we want minimal surprise in fine-tuning. But quality ceiling is probably lower than EmbeddingGemma.

### 3. nomic-embed-text-v2-moe

**Architecture:** MoE text embedder — 475M total params, 305M active per forward pass. 100+ langs.

**Numbers:** Claims "SOTA multilingual MIRACL for its size." Trained on BEIR + MIRACL training sets directly (potential test-set leakage concern on any MIRACL eval — we use our own dev, so moot).

**License:** **Apache-2.0**.

**Risks:**
- MoE routing adds training-time complexity — fine-tuning needs router unfreezing decisions, expert balance loss. Non-trivial on Colab T4.
- Less battle-tested in Sentence-Transformers fine-tune recipes; we'd be the early adopter.
- Total size 475M means full-precision weights load is comparable to BGE-m3; MoE savings only matter at scale.

**Rationale for third:** Strong claimed multilingual performance but MoE fine-tune is a research project in itself. Pair-data + recipe iteration is hard enough — don't combine it with a novel architecture.

---

## Verdict

**Top pick: `google/embeddinggemma-300m`.**

**Runner-up: `Alibaba-NLP/gte-multilingual-base`** (only if EmbeddingGemma's license is blocked by product/business review, or if a quick pre-fine-tune zero-shot benchmark on our dev-149 shows it's ahead of EmbeddingGemma on Hindi specifically).

### Decision protocol for Phase 3b

1. **Zero-shot bake-off (half a day of T4 time).** Before fine-tuning anything, run BGE-m3 base, EmbeddingGemma, gte-multilingual, and nomic-v2-moe on our existing dev-149 with NO fine-tune. This is a cheap sanity check — the base that wins out-of-the-box has ≈ +5pt head-start after fine-tune in typical retrieval work.
2. **Fine-tune the top-2 on γ pairs** (see `gamma-pair-mining-spec.md`). Budget 2 epochs each, best-on-dev checkpoint.
3. **Gate:** a candidate passes only if it beats v3+BM25-tuned-hybrid 0.430 by +5% overall (0.452) OR +10% on brand_as_generic.

### Honest caveat (repeated in ADR 017)

ADR 015 documents that four data-augmentation recipes on BGE-m3 all landed in [−6.8%, +2.4%]. Changing the base model is a stronger lever than pair-data-only (new backbone → new inductive biases) — so there's reason to expect >+2.4% from this axis. But it's not guaranteed; we commit to publishing whatever number comes out, not shipping a regression.

---

## Sources

- [EmbeddingGemma on Hugging Face](https://huggingface.co/google/embeddinggemma-300m)
- [Google Developers Blog: Introducing EmbeddingGemma](https://developers.googleblog.com/en/introducing-embeddinggemma/)
- [EmbeddingGemma paper (arXiv 2509.20354)](https://arxiv.org/abs/2509.20354)
- [Gemma Terms of Use](https://ai.google.dev/gemma/terms)
- [Alibaba-NLP/gte-multilingual-base on HF](https://huggingface.co/Alibaba-NLP/gte-multilingual-base)
- [GTE-Multilingual series blog (Alibaba Cloud)](https://www.alibabacloud.com/blog/gte-multilingual-series-a-key-model-for-retrieval-augmented-generation_601776)
- [nomic-ai/nomic-embed-text-v2-moe on HF](https://huggingface.co/nomic-ai/nomic-embed-text-v2-moe)
- [Nomic v2 MoE preprint](https://static.nomic.ai/nomic_embed_multilingual_preprint.pdf)
- [jinaai/jina-embeddings-v3 on HF (CC-BY-NC-4.0)](https://huggingface.co/jinaai/jina-embeddings-v3)
- [BAAI/bge-m3 on HF (baseline)](https://huggingface.co/BAAI/bge-m3)
- [Sarvam-1 on HF (Indic LM, not embedding)](https://huggingface.co/sarvamai/sarvam-1)
- [MMTEB paper (arXiv 2502.13595)](https://arxiv.org/html/2502.13595v4)
