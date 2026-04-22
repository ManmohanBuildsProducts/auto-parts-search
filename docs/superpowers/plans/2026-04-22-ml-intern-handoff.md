# ml-intern Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hand off three tasks to ml-intern — a literature sweep (today), and a cross-encoder distillation training run (after labels are ready) — using the free HF GPU credits.

**Architecture:** Three-phase handoff. Phase A is immediate (no code, just the prompt brief). Phase B generates Claude-judged training labels locally and uploads to HF Hub. Phase C hands the cross-encoder training to ml-intern with a precise brief pointing at the HF dataset.

**Tech Stack:** Python, Anthropic SDK (Haiku for batched judgment), HF Hub datasets library, ml-intern CLI, FastAPI `/search` endpoint (must be running locally).

**Estimated cost:** ~$1.50 in Claude Haiku API calls for label generation. GPU cost: covered by HF credits.

---

## Phase A — Today (no prerequisites)

### Task 1: Install ml-intern

- [ ] **Install the CLI**

```bash
pip install ml-intern
```

Or check the web app at https://github.com/huggingface/ml-intern — use whichever lets you claim the free credits.

- [ ] **Verify login**

```bash
huggingface-cli whoami
# must print: ManmohanBuildsProducts
```

- [ ] **Claim and note the free HF Jobs GPU credits**

Find the "free credits" link from the HF ml-intern launch announcement. Claim them. Note the credit balance — we'll use it for the cross-encoder training run in Phase C.

---

### Task 2: Run the literature sweep (Task #1)

The brief below is the exact prompt to paste into ml-intern. No code required — just paste and let it run.

- [ ] **Save the brief to disk** (for audit trail)

Create `docs/ml-intern-briefs/01-literature-sweep.md` with the following content:

```markdown
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
- Our v3:                0.430
- OpenAI text-embedding-3-large: 0.468  ← target to beat

**Per-category gaps (v3 vs OpenAI):**
- Hindi/Hinglish queries:   v3 0.440 vs OpenAI 0.544  (-10 pts)
- brand_as_generic queries: v3 0.320 vs OpenAI 0.470  (-15 pts)
- part_number queries:      v3 0.084 vs OpenAI 0.178  (-9 pts, routing to BM25 handles this)
- symptom queries:          v3 0.390 vs OpenAI 0.450  (-6 pts)

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
- Claude (Anthropic) distillation is allowed.
- Must handle Devanagari + Roman script queries against English-dominant catalog docs.
- No new base model exploration needed right now — focus on training data strategies
  and reranker architectures on top of BGE-m3.
```

- [ ] **Paste the brief into ml-intern and run it**

```bash
ml-intern run --file docs/ml-intern-briefs/01-literature-sweep.md
```

Or paste into the web app. Expected runtime: 2-3 hours autonomous.

- [ ] **Save the output**

When ml-intern finishes, save its full output to:

```
docs/ml-intern-briefs/01-literature-sweep-output.md
```

- [ ] **Filter the output through `memory/findings.md`**

Read the output. Cross-check each suggested technique against findings #9 (data augmentation saturated on BGE-m3) and #10 (part_number is structural, not embedding). Discard suggestions that fall into either category. Keep only suggestions that are genuinely new to this repo.

---

## Phase B — This week (requires running code)

Phase B generates the Claude-judged (query, doc, label) pairs that ml-intern needs for Phase C. Two scripts to write and run.

**Prerequisite:** FastAPI server must be running locally (`bash scripts/start_all.sh`).

---

### Task 3: Write `scripts/generate_training_queries.py`

Generates synthetic customer queries from catalog docs. ~1K sampled docs × 5 queries = 5K training queries.

**Files:**
- Create: `scripts/generate_training_queries.py`
- Output: `data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl`

- [ ] **Write the script**

```python
"""Generate synthetic training queries from catalog docs for reranker distillation.

Samples N catalog docs from Meilisearch, calls Claude Haiku to generate K realistic
customer queries per doc. Output: JSONL of {query, doc_id, doc_title, doc_snippet}.

Usage:
    python3 -m scripts.generate_training_queries --n-docs 1000 --queries-per-doc 5
"""
from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import anthropic
import requests

API_BASE = "http://127.0.0.1:8000"
MEILI_BASE = "http://127.0.0.1:7700"
OUT_DIR = Path("data/training/experiments/2026-04-22-ml-intern")
SEED = 42

QUERY_GEN_PROMPT = """You are a customer searching for auto parts on an Indian e-commerce site.
Given the product below, write {k} realistic search queries a customer might type to find it.
Include variety: Hindi/Hinglish queries, symptom-based queries, brand+part queries, misspellings.
Return ONLY a JSON array of strings. No prose, no markdown.

Product: {title}"""


def fetch_all_doc_ids(limit: int) -> list[dict]:
    """Pull a random sample of catalog docs from Meilisearch."""
    r = requests.post(
        f"{MEILI_BASE}/indexes/parts/search",
        json={"q": "", "limit": limit, "filter": "doc_type = 'catalog'"},
    )
    r.raise_for_status()
    return r.json()["hits"]


def generate_queries_for_doc(client: anthropic.Anthropic, doc: dict, k: int) -> list[str]:
    title = doc.get("title") or doc.get("name") or ""
    if not title.strip():
        return []
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        messages=[{"role": "user", "content": QUERY_GEN_PROMPT.format(title=title, k=k)}],
    )
    raw = msg.content[0].text.strip()
    try:
        queries = json.loads(raw)
        return [q for q in queries if isinstance(q, str) and q.strip()][:k]
    except json.JSONDecodeError:
        return []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-docs", type=int, default=1000)
    parser.add_argument("--queries-per-doc", type=int, default=5)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "training_queries.jsonl"

    client = anthropic.Anthropic()

    print(f"fetching {args.n_docs} catalog docs from Meilisearch...")
    docs = fetch_all_doc_ids(limit=10000)  # fetch more, then sample
    random.seed(SEED)
    docs = random.sample(docs, min(args.n_docs, len(docs)))
    print(f"sampled {len(docs)} docs")

    written = 0
    with out_path.open("w") as f:
        for i, doc in enumerate(docs):
            queries = generate_queries_for_doc(client, doc, args.queries_per_doc)
            for q in queries:
                record = {
                    "query": q,
                    "doc_id": doc.get("id") or doc.get("_id") or str(i),
                    "doc_title": doc.get("title") or doc.get("name") or "",
                    "doc_snippet": (doc.get("title") or "")[:200],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1
            if (i + 1) % 50 == 0:
                print(f"  {i+1}/{len(docs)} docs done, {written} queries written")
            time.sleep(0.1)  # stay under rate limit

    print(f"done: {written} queries → {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Run it and verify output**

```bash
python3 -m scripts.generate_training_queries --n-docs 1000 --queries-per-doc 5
```

Expected: `data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl` with ~5K lines.

```bash
wc -l data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl
# expect: 4500–5100
head -3 data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl
# expect: 3 JSON objects each with query, doc_id, doc_title, doc_snippet
```

---

### Task 4: Write `scripts/generate_judgment_labels.py`

For each training query, retrieves top-20 candidates from our hybrid search, then asks Claude Haiku to judge relevance in batches of 10 pairs. Cost: ~$1.50.

**Files:**
- Create: `scripts/generate_judgment_labels.py`
- Input: `data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl`
- Output: `data/training/experiments/2026-04-22-ml-intern/judgment_labels.jsonl`

- [ ] **Write the script**

```python
"""Generate (query, doc, label) triples for cross-encoder reranker training.

For each query in training_queries.jsonl:
  1. Retrieve top-20 candidates from /search
  2. Batch 10 (query, doc) pairs per Claude Haiku call for relevance judgment
  3. Output JSONL of {query, doc_id, doc_title, doc_text, label}

Labels: 0=irrelevant, 1=marginal, 2=relevant (same scale as judge_benchmark.py)

Usage:
    python3 -m scripts.generate_judgment_labels
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import anthropic
import requests

API_BASE = "http://127.0.0.1:8000"
IN_PATH = Path("data/training/experiments/2026-04-22-ml-intern/training_queries.jsonl")
OUT_PATH = Path("data/training/experiments/2026-04-22-ml-intern/judgment_labels.jsonl")

JUDGE_SYSTEM = """You are an expert Indian auto-parts mechanic grading search relevance.
For each (Query, Doc) pair, assign:
  2 = RELEVANT: exact match, correct synonym, or the part that fixes the described symptom
  1 = MARGINAL: related part, same system, adjacent — but not the direct answer
  0 = IRRELEVANT: wrong part entirely

Return ONLY a JSON array of integers, one per pair. No prose."""


def search_top_k(query: str, k: int = 20) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE}/search", params={"q": query, "top_k": k}, timeout=10)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


def judge_batch(client: anthropic.Anthropic, query: str, docs: list[dict]) -> list[int]:
    """Judge up to 10 (query, doc) pairs in a single call."""
    pairs_text = "\n".join(
        f"Pair {i+1}: Query={query!r} | Doc={d.get('title','')[:120]!r}"
        for i, d in enumerate(docs)
    )
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=64,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": pairs_text}],
    )
    raw = msg.content[0].text.strip()
    try:
        scores = json.loads(raw)
        if isinstance(scores, list) and len(scores) == len(docs):
            return [max(0, min(2, int(s))) for s in scores]
    except (json.JSONDecodeError, ValueError):
        pass
    return [0] * len(docs)  # fallback: mark all irrelevant on parse failure


def main() -> None:
    client = anthropic.Anthropic()
    queries = [json.loads(l) for l in IN_PATH.read_text().splitlines() if l.strip()]
    print(f"loaded {len(queries)} training queries")

    seen_pairs: set[tuple[str, str]] = set()
    # Resume from existing output
    if OUT_PATH.exists():
        for line in OUT_PATH.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                seen_pairs.add((rec["query"], rec["doc_id"]))
        print(f"resuming: {len(seen_pairs)} pairs already done")

    written = 0
    with OUT_PATH.open("a") as f:
        for i, q_rec in enumerate(queries):
            query = q_rec["query"]
            candidates = search_top_k(query, k=20)
            # Skip already-judged
            candidates = [c for c in candidates if (query, str(c.get("id", ""))) not in seen_pairs]
            if not candidates:
                continue

            # Judge in batches of 10
            batch_size = 10
            for b_start in range(0, len(candidates), batch_size):
                batch = candidates[b_start : b_start + batch_size]
                scores = judge_batch(client, query, batch)
                for doc, label in zip(batch, scores):
                    doc_id = str(doc.get("id") or doc.get("_id") or "")
                    record = {
                        "query": query,
                        "doc_id": doc_id,
                        "doc_title": doc.get("title") or doc.get("name") or "",
                        "doc_text": (doc.get("title") or "")[:300],
                        "label": label,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    written += 1
                time.sleep(0.05)

            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(queries)} queries done, {written} new labels written")

    print(f"done: {written} judgment labels → {OUT_PATH}")


if __name__ == "__main__":
    main()
```

- [ ] **Run it (start_all.sh must be running first)**

```bash
bash scripts/start_all.sh   # if not already running
python3 -m scripts.generate_judgment_labels
```

Expected runtime: ~30-45 min for 5K queries × 20 candidates. Expected output: ~80K-100K lines in `judgment_labels.jsonl`.

- [ ] **Verify label distribution**

```bash
python3 -c "
import json
from pathlib import Path
from collections import Counter
labels = [json.loads(l)['label'] for l in Path('data/training/experiments/2026-04-22-ml-intern/judgment_labels.jsonl').read_text().splitlines() if l.strip()]
print(Counter(labels))
print(f'total: {len(labels)}')
"
```

Expected: label 0 dominant (~60%), label 2 at ~15-25%. If label 2 is <5%, the search or judge is broken — check `/search` is returning results and Claude is parsing correctly.

---

### Task 5: Upload judgment labels to HF Hub

- [ ] **Write the upload script inline and run it**

```bash
python3 - <<'EOF'
import json
from pathlib import Path
from datasets import Dataset
from huggingface_hub import HfApi

src = Path("data/training/experiments/2026-04-22-ml-intern/judgment_labels.jsonl")
records = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
print(f"loaded {len(records)} records")

repo = "ManmohanBuildsProducts/auto-parts-reranker-training"
HfApi().create_repo(repo_id=repo, repo_type="dataset", private=True, exist_ok=True)

ds = Dataset.from_list(records)
ds.push_to_hub(repo, private=True, commit_message="judgment labels v1 — Claude Haiku judge, 5K queries × top-20")
print(f"pushed to https://huggingface.co/datasets/{repo}")
EOF
```

- [ ] **Confirm the dataset landed**

```bash
python3 -c "
from datasets import load_dataset
ds = load_dataset('ManmohanBuildsProducts/auto-parts-reranker-training', split='train')
print(ds)
print(ds[0])
"
```

Expected: Dataset with columns `query`, `doc_id`, `doc_title`, `doc_text`, `label` and 80K+ rows.

---

## Phase C — After Phase B is done

### Task 6: Run the cross-encoder distillation brief on ml-intern

- [ ] **Save the brief**

Create `docs/ml-intern-briefs/03-cross-encoder-distillation.md`:

```markdown
I need to fine-tune a cross-encoder reranker on a domain-specific (query, doc, relevance)
dataset and evaluate it against my existing retrieval benchmark.

**HF dataset:** `ManmohanBuildsProducts/auto-parts-reranker-training` (private)
Columns: query (str), doc_id (str), doc_title (str), doc_text (str), label (int 0/1/2)
Labels generated by Claude Haiku judge. Domain: Indian auto-parts (Hindi/Hinglish + English).
~80-100K training triples.

**Base model for cross-encoder:** `BAAI/bge-reranker-v2-m3`
(multilingual cross-encoder, supports Hindi + English, 568M params)

**Evaluation benchmark:** `ManmohanBuildsProducts/auto-parts-search-benchmark` (public)
149 graded queries (0/1/2 labels, same scale as training). Metric: nDCG@10.
First-stage retrieval baseline (before reranking): 0.430 nDCG@10.
Target: ≥ 0.468 nDCG@10 (match OpenAI text-embedding-3-large).

**What I need:**
1. Fine-tune `BAAI/bge-reranker-v2-m3` on the training dataset using the graded labels.
   Use a loss that handles 0/1/2 graded relevance (not just binary BCE).
   Suggested approach: regression loss on normalized labels (0, 0.5, 1.0) or
   listwise LambdaLoss if it improves nDCG.
2. Evaluate the fine-tuned reranker: for each of the 149 benchmark queries, rerank
   the top-20 candidates from our first-stage retriever using the cross-encoder score,
   then compute nDCG@10.
3. Run at least 2 ablations:
   - Learning rate: 2e-5 vs 5e-5
   - Epochs: 3 vs 5
4. Push the best checkpoint to `ManmohanBuildsProducts/auto-parts-reranker-v1` (private).

**Compute:** Use A100 on HF Jobs. Training budget: 2 hrs max.

**Hard constraints:**
- Do NOT use OpenAI API for any step (ToS restriction).
- Claude API is allowed.
- The reranker runs at inference on top of our existing dense retriever — it does not
  replace it. Inference budget: ≤ 200ms per query for top-20 reranking.
```

- [ ] **Run it**

```bash
ml-intern run --file docs/ml-intern-briefs/03-cross-encoder-distillation.md
```

Expected runtime: 2-4 hours (A100 training + ablations). Cost: covered by HF credits.

- [ ] **Verify the pushed checkpoint exists**

```bash
python3 -c "
from huggingface_hub import HfApi
info = HfApi().model_info('ManmohanBuildsProducts/auto-parts-reranker-v1')
print(info.modelId, info.lastModified)
"
```

- [ ] **Plug the reranker into `auto_parts_search/api.py` and re-run bench**

This step is done by us (Claude Code), not ml-intern. Create a follow-up task once the checkpoint exists.

---

## Self-review checklist

- [x] Phase A: no code dependency, can run today
- [x] Phase B scripts are incremental (append-mode, resume on crash)
- [x] Label generation cost bounded (~$1.50 at Haiku prices for 5K queries)
- [x] HF upload uses same pattern as existing `upload_pairs_to_hf.py`
- [x] Both ml-intern briefs are self-contained — no internal code references, no local paths
- [x] Cross-encoder brief avoids OpenAI (ToS constraint from `memory/findings.md` #4 + TASKS.md T670)
- [x] Evaluation metric is concrete (nDCG@10, same scale as our existing benchmark)
- [x] Phase C is clearly gated on Phase B completion
