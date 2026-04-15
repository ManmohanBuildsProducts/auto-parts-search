---
license: apache-2.0
language:
  - en
  - hi
base_model: BAAI/bge-m3
library_name: sentence-transformers
pipeline_tag: sentence-similarity
tags:
  - sentence-transformers
  - sentence-similarity
  - feature-extraction
  - retrieval
  - indic
  - hindi
  - hinglish
  - auto-parts
  - e-commerce
datasets:
  - ManmohanBuildsProducts/auto-parts-search-benchmark
metrics:
  - ndcg
  - recall
  - map
  - mrr
---

# auto-parts-search-v3

> A **1024-dim multilingual embedding model fine-tuned for Indian auto-parts retrieval** — Hindi, Hinglish, English, misspellings, brand-as-generic usage, symptom queries, and part-number lookups.

**Fine-tuned from:** [`BAAI/bge-m3`](https://huggingface.co/BAAI/bge-m3) (MIT) using 26,760 domain-specific pairs + `MultipleNegativesRankingLoss`.

## TL;DR — public benchmark results

On the [`auto-parts-search-benchmark`](https://huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-benchmark) dev set (149 queries, joint-pool LLM-judged by DeepSeek V3):

| Model | nDCG@10 | R@5 | P@1 | MAP@10 | $/1M tok |
|---|---:|---:|---:|---:|---:|
| openai/text-embedding-3-large | **0.468** | 0.290 | 0.550 | 0.477 | $0.13 |
| **v3 + BM25 hybrid (tuned, 3-fold CV)** | **0.424** | **0.257** | **0.523** | **0.458** | **$0** |
| **v3 (embedding only)** | 0.411 | 0.240 | 0.503 | 0.439 | **$0** |
| cohere/embed-multilingual-v3.0 | 0.332 | 0.218 | 0.456 | 0.379 | $0.10 |
| intfloat/multilingual-e5-large | 0.309 | 0.221 | 0.450 | 0.360 | $0 |
| BAAI/bge-m3 (base) | 0.307 | 0.194 | 0.403 | 0.328 | $0 |

(Corpus = 26,835 docs: 884 KG parts + 25,951 catalog products. Full methodology in [`EVAL_REPORT.md`](https://huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-benchmark/blob/main/EVAL_REPORT.md).)

**Headline:** v3 is #2 of 5 commercial + open-source embedding models on this benchmark, while running on CPU at $0/query. Beats its own BGE-m3 base by **+34%** overall, **+43%** on brand-as-generic, and **+50%** on symptom queries (per-category on production corpus).

### Per-category nDCG@10 — where v3 wins and loses

| Category | v3 + BM25 (tuned) | OpenAI | Δ |
|---|---:|---:|---:|
| exact_english (n=27) | **0.531** | 0.480 | **+5.1** ✅ |
| misspelled (n=23) | **0.544** | 0.526 | **+1.8** ✅ |
| symptom (n=27) | 0.497 | 0.555 | -5.8 |
| hindi_hinglish (n=27) | 0.460 | 0.544 | -8.4 |
| brand_as_generic (n=22) | 0.415 | 0.499 | -8.4 |
| part_number (n=23) | 0.099 | 0.178 | -7.9 |

v3 wins on exact-English and misspelled queries. It trails on Hindi + brand + part_number — the "catalog-style" categories where v3 wasn't trained. Those gaps are targeted in Phase 3b (see project ADR 017).

## Usage

### Option 1: `sentence-transformers` (recommended)

```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer("ManmohanBuildsProducts/auto-parts-search-v3")

corpus = [
    "Brake pad (front) for Maruti Suzuki Swift",
    "Engine oil filter, universal fit",
    "Spark plug | Bosch | system: Ignition",
]
queries = ["patti badal do swift ki", "oil filter Swift"]

corpus_emb = model.encode(corpus, normalize_embeddings=True)
query_emb = model.encode(queries, normalize_embeddings=True)

sims = query_emb @ corpus_emb.T  # (2, 3) cosine scores
```

No query/doc prefix. Output is 1024-dim, L2-normalized.

### Option 2: HuggingFace Transformers

```python
from transformers import AutoTokenizer, AutoModel
import torch

tok = AutoTokenizer.from_pretrained("ManmohanBuildsProducts/auto-parts-search-v3")
model = AutoModel.from_pretrained("ManmohanBuildsProducts/auto-parts-search-v3")

inputs = tok(["brake pad"], padding=True, truncation=True, return_tensors="pt")
with torch.no_grad():
    out = model(**inputs)
# CLS token, then L2-normalize
emb = torch.nn.functional.normalize(out.last_hidden_state[:, 0], p=2, dim=1)
```

### Option 3: Production hybrid (best results)

The headline hybrid number combines v3 embeddings + Meilisearch BM25 + class-weighted Reciprocal Rank Fusion. See [github.com/ManmohanBuildsProducts/auto-parts-search](https://github.com/ManmohanBuildsProducts/auto-parts-search) for the full pipeline.

## Training details

- **Base:** `BAAI/bge-m3` (multilingual, 568M params, 1024-dim)
- **Pairs:** 26,760 positive + negative triples; sources in [`data/training/golden/METADATA.md`](https://github.com/ManmohanBuildsProducts/auto-parts-search/blob/master/data/training/golden/METADATA.md)
  - Vocabulary synonyms / misspellings / symptom / brand-generic (7.8K positive)
  - HSN-taxonomy siblings/cousins (graded 0.85 / 0.40)
  - Catalog-group positives (3-part and 2-part groupings)
  - System-membership + symptom-part links
  - Hard negatives (12.5K)
- **Loss:** `MultipleNegativesRankingLoss` (MNR); batch size 32; temperature 0.05
- **Base model improvement:** +21.8% MRR over BGE-m3 on dev set at Phase 3 closing gate
- **Deterministic regeneration:** all pair generators seeded with `random.Random(42)`; pair file SHA256 `7157b63450bb0399…`
- **Reproducibility snapshot:** [`ManmohanBuildsProducts/auto-parts-search-raw`](https://huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-raw) tag `scrape-v3-2026-04-13`

## Intended use

- Retrieval over Indian auto-parts catalogs (KG + e-commerce scrape)
- Hindi/Hinglish query handling
- Symptom-based part lookup
- Use in a hybrid stack with BM25 for part numbers (v3 alone scores 0.084 on PN)

## Limitations

1. **Not for general-purpose retrieval.** Fine-tuned on one vertical.
2. **Part-number-free.** Embedding model can't exact-match PNs; pair with BM25 + filters.
3. **Dev-set n = 149.** Per-category MoE ≈ ±10%. See limitations section in [EVAL_REPORT](https://huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-benchmark/blob/main/EVAL_REPORT.md).
4. **Judge is DeepSeek V3, not human** — 96% query-level agreement with Claude Opus on this task (calibrated 2026-04-13).

## License

**Apache-2.0.** The base model (BGE-m3) is MIT-licensed; this derivative is released under Apache-2.0 for patent grant. Commercial use permitted; attribution requested.

## Citation

```bibtex
@misc{auto_parts_search_v3_2026,
  author    = {Khurana, Manmohan},
  title     = {auto-parts-search-v3: A Hindi/Hinglish-aware embedding model for Indian auto-parts retrieval},
  year      = 2026,
  publisher = {Hugging Face},
  url       = {https://huggingface.co/ManmohanBuildsProducts/auto-parts-search-v3},
}
```

## Contact

Manmohan Khurana — `manmohanbuildsproducts [at] gmail.com`
Building an Indic-first auto-parts search product. Looking for Indian e-commerce pilots.
