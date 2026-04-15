# Eval — Round 2 (T305 production-scale benchmark)

Corpus: 26,835 docs (884 KG + 25,951 catalog). Queries: 149 dev. Judge: DeepSeek V3.

## Overall scoreboard

| Model | nDCG@10 | Recall@5 | P@1 | MAP@10 | 0-result% |
|---|---:|---:|---:|---:|---:|
| `openai-3-large` | 0.468 | 0.290 | 0.550 | 0.477 | 32.9% |
| `cohere-mult-v3` | 0.332 | 0.218 | 0.456 | 0.379 | 36.2% |
| `e5-large` | 0.309 | 0.221 | 0.450 | 0.360 | 36.9% |
| `bge-m3` | 0.307 | 0.194 | 0.403 | 0.328 | 35.6% |
| `v3-ours` | 0.411 | 0.240 | 0.503 | 0.439 | 34.9% |
| `v3+bm25-hybrid` | 0.400 | 0.242 | 0.483 | 0.426 | 33.6% |
| `v3+bm25-hybrid-tuned` | 0.430 | 0.257 | 0.523 | 0.458 | 33.6% |

## Per-category nDCG@10

| Model | brand_as_generic (n=22) | exact_english (n=27) | hindi_hinglish (n=27) | misspelled (n=23) | part_number (n=23) | symptom (n=27) |
|---|---|---|---|---|---|---|
| `openai-3-large` | 0.499 | 0.480 | 0.544 | 0.526 | 0.178 | 0.555 |
| `cohere-mult-v3` | 0.369 | 0.413 | 0.380 | 0.432 | 0.068 | 0.313 |
| `e5-large` | 0.410 | 0.296 | 0.382 | 0.474 | 0.047 | 0.252 |
| `bge-m3` | 0.311 | 0.287 | 0.360 | 0.439 | 0.056 | 0.373 |
| `v3-ours` | 0.353 | 0.514 | 0.440 | 0.538 | 0.084 | 0.495 |
| `v3+bm25-hybrid` | 0.346 | 0.451 | 0.451 | 0.525 | 0.127 | 0.468 |
| `v3+bm25-hybrid-tuned` | 0.415 | 0.531 | 0.460 | 0.544 | 0.099 | 0.497 |
