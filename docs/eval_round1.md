# Eval — Round 1 (T305 external benchmark)

Corpus: 2,121 KG docs (v3-ranked subset). Queries: 149 dev. Joint-pool judged by DeepSeek R1.

Metric set: nDCG@10 (graded), Recall@5 (grade=2), P@1, MAP@10 (binary), zero-result@10 + per-category nDCG@10.

## Overall scoreboard

| Model | nDCG@10 | Recall@5 | P@1 | MAP@10 | 0-result% |
|---|---:|---:|---:|---:|---:|
| `openai-3-large` | 0.539 | 0.483 | 0.611 | 0.466 | 16.1% |
| `cohere-mult-v3` | 0.395 | 0.317 | 0.591 | 0.461 | 20.1% |
| `jina-v3` | 0.388 | 0.300 | 0.523 | 0.464 | 26.8% |
| `e5-large` | 0.356 | 0.318 | 0.523 | 0.420 | 21.5% |
| `bge-m3` | 0.369 | 0.347 | 0.490 | 0.391 | 24.2% |
| `v3-ours` | 0.477 | 0.378 | 0.631 | 0.505 | 21.5% |
| `v3+bm25-hybrid` | 0.461 | 0.389 | 0.570 | 0.468 | 20.8% |

## Per-category nDCG@10

| Model | brand_as_generic (n=22) | exact_english (n=27) | hindi_hinglish (n=27) | misspelled (n=23) | part_number (n=23) | symptom (n=27) |
|---|---|---|---|---|---|---|
| `openai-3-large` | 0.601 | 0.732 | 0.526 | 0.595 | 0.252 | 0.503 |
| `cohere-mult-v3` | 0.363 | 0.609 | 0.393 | 0.500 | 0.096 | 0.376 |
| `jina-v3` | 0.374 | 0.545 | 0.483 | 0.521 | 0.073 | 0.301 |
| `e5-large` | 0.343 | 0.497 | 0.351 | 0.527 | 0.099 | 0.304 |
| `bge-m3` | 0.324 | 0.582 | 0.360 | 0.531 | 0.082 | 0.309 |
| `v3-ours` | 0.436 | 0.675 | 0.548 | 0.637 | 0.106 | 0.424 |
| `v3+bm25-hybrid` | 0.428 | 0.638 | 0.519 | 0.611 | 0.117 | 0.419 |
