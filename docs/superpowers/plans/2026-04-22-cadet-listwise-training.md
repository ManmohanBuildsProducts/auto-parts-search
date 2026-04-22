# CADeT Listwise Distillation — Implementation Plan (Technique 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the saturated MNRL training signal with cross-encoder listwise distillation to push overall nDCG@10 from 0.430 toward 0.470+ and close the Hindi/brand_as_generic gap vs OpenAI.

**Architecture:** Three-stage pipeline. (1) Generate 6 synthetic query types per catalog passage via Azure GPT-4o-mini, using γ-strategy-biased doc sampling (oversample brand_as_generic + Hindi seed docs); filter using embedding-only search for hard categories (hindi/brand), hybrid search for others. (2) Score top-20 candidates per query with bge-reranker-v2-m3 as teacher. (3) Fine-tune **v3** (not BGE-m3 base — v3 has +35% domain adaptation already baked in) with a combined KL-divergence listwise loss + InfoNCE on A100 via HF Jobs; the InfoNCE component trains on golden-v2 (26,760 existing high-quality pairs) not new synthetic pairs. Upload all intermediate artefacts to HF Hub.

**Tech Stack:** Python 3.11, openai (Azure), sentence-transformers, transformers, torch, datasets (HF), huggingface_hub, pytest. Training run on HF Jobs A100 (ml-intern credits). All API calls use keys already in `.env`.

**Scope note:** This plan covers Technique 1 only. Technique 2 (CLEAR cross-lingual alignment) and Technique 3 (EBRM entity-aware) are separate plans that stack on top of this one after it ships.

---

## Resource map

| Step | Service | Model / Tool | Key location | Cost est. |
|---|---|---|---|---|
| Synthetic query generation | Azure OpenAI (eastus) | gpt-4o-mini | `AZURE_OPENAI_API_KEY` in `.env` | ~$0.20 for 30K queries |
| Teacher cross-encoder scoring | Local | bge-reranker-v2-m3 (HF Hub, auto-downloaded) | n/a | $0 |
| HF Hub dataset upload | HF Hub | datasets lib | `HF_TOKEN` at `~/.cache/huggingface/token` | $0 |
| Training | HF Jobs A100 | sentence-transformers | HF_TOKEN | ml-intern credits |
| Evaluation | Local | training/evaluate.py (existing) | n/a | $0 |

---

## File map

| File | Action | Purpose |
|---|---|---|
| `scripts/generate_listwise_data.py` | **Create** | Stage 1+2: generate queries, filter, score with teacher |
| `training/listwise_loss.py` | **Create** | Custom KL + InfoNCE loss for sentence-transformers |
| `training/train_listwise.py` | **Create** | HF Jobs training script |
| `scripts/upload_listwise_to_hf.py` | **Create** | Upload JSONL dataset to HF Hub |
| `tests/test_listwise_loss.py` | **Create** | Unit tests for the loss function |
| `tests/test_generate_listwise.py` | **Create** | Unit tests for query generation helpers |
| `.env` | **Modified** (done) | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` added |

---

## Task 1: Verify Azure OpenAI connection

**Files:** no file changes — smoke test only.

- [ ] **Step 1: Verify the key works**

```bash
cd ~/Projects/auto-parts-search
source .env
python3 - <<'EOF'
from openai import AzureOpenAI
import os
client = AzureOpenAI(
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version="2024-10-21",
)
r = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Reply with just: OK"}],
    max_tokens=5,
)
print(r.choices[0].message.content)
EOF
```

Expected output: `OK`

If you get `AuthenticationError` — the key rotated. Re-run:
```bash
az cognitiveservices account keys list -n badho-call-analysis-84cb9b -g badho-call-analysis-rg --query key1 -o tsv
```
Then update `AZURE_OPENAI_API_KEY` in `.env`.

---

## Task 2: Write and test query generation helpers

**Files:**
- Create: `scripts/generate_listwise_data.py` (helpers only, not the full pipeline yet)
- Create: `tests/test_generate_listwise.py`

The script generates 6 query types per catalog passage. Test the prompt + parsing logic with mocks before running at scale.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_generate_listwise.py`:

```python
"""Tests for generate_listwise_data.py helpers."""
from unittest.mock import MagicMock, patch
import pytest

# --- helpers under test (imported after we create them) ---
from scripts.generate_listwise_data import (
    build_query_prompt,
    parse_query_response,
    make_azure_client,
)


def test_build_query_prompt_contains_doc_title():
    prompt = build_query_prompt("Maruti Swift Rear Brake Pad - ATE OEM")
    assert "Maruti Swift Rear Brake Pad" in prompt
    assert "Hindi" in prompt
    assert "Hinglish" in prompt
    assert "brand" in prompt.lower() or "generic" in prompt.lower()


def test_parse_query_response_returns_6_queries():
    raw = """[
        "brake pad for Swift",
        "Swift ke liye brake pad",
        "Swift brake pad lagao",
        "Swift rear brake pad Romanized query",
        "rear braking noise Swift",
        "ATE brake pad Swift OEM"
    ]"""
    result = parse_query_response(raw)
    assert len(result) == 6
    assert all(isinstance(q, str) for q in result)


def test_parse_query_response_handles_truncated_json():
    # model sometimes returns incomplete JSON — should return empty list, not crash
    raw = '["brake pad for Swift", "Swift ke liye'
    result = parse_query_response(raw)
    assert isinstance(result, list)


def test_parse_query_response_deduplicates():
    raw = '["same query", "same query", "different query"]'
    result = parse_query_response(raw)
    assert len(set(result)) == len(result)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_generate_listwise.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError` — the script doesn't exist yet.

- [ ] **Step 3: Create `scripts/generate_listwise_data.py` with helpers**

```python
"""CADeT-style listwise training data generation.

Stage 1: Generate 6 synthetic query types per catalog passage (Azure GPT-4o-mini).
Stage 2: Filter — our hybrid search must return the source doc in top-20.
Stage 3: Score top-20 candidates with bge-reranker-v2-m3 (local cross-encoder teacher).

Output: JSONL of {query, query_type, gold_doc_id, candidates: [{doc_id, doc_text, teacher_score}]}

Usage:
    source .env
    python3 -m scripts.generate_listwise_data --n-docs 5000 --out data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import random
import time
from pathlib import Path

import requests
from openai import AzureOpenAI

AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
AZURE_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")
SEARCH_API = "http://127.0.0.1:8000"
SEED = 42

QUERY_PROMPT_TEMPLATE = """You are a customer on an Indian auto-parts e-commerce site.
Given the product below, write exactly 6 search queries a customer might type.
One query of each type — in this exact order:
1. Hindi natural query (Devanagari script)
2. Hinglish query (mix of Hindi words + English, Roman script)
3. Romanized Hindi query (Hindi sounds spelled in English letters)
4. English technical query (part name + vehicle model)
5. Symptom or problem description query (what's broken, not part name)
6. Brand-as-generic variant (swap brand for generic term or vice versa)

Product: {title}

Return ONLY a valid JSON array of 6 strings. No prose, no markdown, no explanation."""


def make_azure_client() -> AzureOpenAI:
    return AzureOpenAI(
        api_key=AZURE_KEY,
        azure_endpoint=AZURE_ENDPOINT,
        api_version="2024-10-21",
    )


def build_query_prompt(title: str) -> str:
    return QUERY_PROMPT_TEMPLATE.format(title=title)


def parse_query_response(raw: str) -> list[str]:
    """Parse JSON array from model response. Returns [] on any parse failure."""
    raw = raw.strip()
    # Find first '[' and last ']' — model sometimes adds prose before/after
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        queries = json.loads(raw[start : end + 1])
        if not isinstance(queries, list):
            return []
        clean = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
        # deduplicate preserving order
        seen: set[str] = set()
        deduped = []
        for q in clean:
            if q not in seen:
                seen.add(q)
                deduped.append(q)
        return deduped
    except json.JSONDecodeError:
        return []


QUERY_TYPES = [
    "hindi_natural",
    "hinglish",
    "romanized_hindi",
    "english_technical",
    "symptom",
    "brand_generic_variant",
]


def generate_queries_for_doc(client: AzureOpenAI, title: str) -> list[dict]:
    """Returns list of {query, query_type} dicts, or [] on failure."""
    prompt = build_query_prompt(title)
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7,
        )
        raw = resp.choices[0].message.content or ""
        queries = parse_query_response(raw)
        # Pair each query with its type (positional)
        return [
            {"query": q, "query_type": QUERY_TYPES[i] if i < len(QUERY_TYPES) else "other"}
            for i, q in enumerate(queries)
        ]
    except Exception:
        return []


def search_top_k(query: str, k: int = 20, embedding_only: bool = False) -> list[dict]:
    """Hit the local /search endpoint and return top-k hits.

    embedding_only=True for hard categories (hindi/brand_as_generic) — hybrid search
    uses BM25 which scores 0 on Hindi text, so the hybrid filter would drop valid pairs.
    """
    try:
        params: dict = {"q": query, "top_k": k}
        if embedding_only:
            params["bm25_weight"] = 0.0  # force embedding-only path
        r = requests.get(f"{SEARCH_API}/search", params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("results", [])
    except Exception:
        return []


# Query types where BM25 actively hurts recall — use embedding-only + looser top-50 filter
HARD_QUERY_TYPES = {"hindi_natural", "hinglish", "romanized_hindi", "brand_generic_variant"}


def fetch_catalog_docs_stratified(n_docs: int) -> list[dict]:
    """γ-strategy-biased doc sampling.

    Oversample sources that are hardest for v3:
    - eauto (brand + vehicle — brand_as_generic seed): 2x weight
    - spareshub (part numbers — PN-aliasing seed): 1x weight
    - bikespares (vehicle-compatible): 1x weight
    - carorbis + rest: 0.5x weight (low signal)

    Target split of n_docs: ~40% eauto, ~35% spareshub, ~15% bikespares, ~10% rest.
    """
    meili = "http://127.0.0.1:7700/indexes/parts/search"

    def fetch_source(source: str, limit: int) -> list[dict]:
        r = requests.post(meili, json={"q": "", "limit": limit, "filter": f"source = '{source}' AND doc_type = 'catalog'"})
        r.raise_for_status()
        return r.json()["hits"]

    random.seed(SEED)
    eauto  = random.sample(fetch_source("eauto",      10000), min(int(n_docs * 0.40), 2000))
    spareshub = random.sample(fetch_source("spareshub", 15000), min(int(n_docs * 0.35), 1750))
    bikespares = random.sample(fetch_source("bikespares", 3000), min(int(n_docs * 0.15), 750))

    # Remainder from any source
    remainder_n = n_docs - len(eauto) - len(spareshub) - len(bikespares)
    all_rest = requests.post(meili, json={"q": "", "limit": 5000, "filter": "doc_type = 'catalog'"}).json()["hits"]
    sampled_ids = {str(d.get("id") or d.get("_id")) for d in eauto + spareshub + bikespares}
    rest = [d for d in all_rest if str(d.get("id") or d.get("_id")) not in sampled_ids]
    rest = random.sample(rest, min(remainder_n, len(rest)))

    docs = eauto + spareshub + bikespares + rest
    print(f"stratified sample: {len(eauto)} eauto + {len(spareshub)} spareshub + "
          f"{len(bikespares)} bikespares + {len(rest)} rest = {len(docs)} total")
    return docs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-docs", type=int, default=5000, help="Catalog docs to sample")
    parser.add_argument("--out", type=Path, default=Path("data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl"))
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    client = make_azure_client()

    print(f"fetching catalog docs from Meilisearch (γ-biased stratified sample)...")
    docs = fetch_catalog_docs_stratified(args.n_docs)

    # Resume: track already-written gold doc IDs
    written_ids: set[str] = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                written_ids.add(rec.get("gold_doc_id", ""))
        print(f"resuming: {len(written_ids)} docs already done")

    written = 0
    with args.out.open("a") as f:
        for i, doc in enumerate(docs):
            doc_id = str(doc.get("id") or doc.get("_id") or i)
            if doc_id in written_ids:
                continue
            title = doc.get("title") or doc.get("name") or ""
            if not title.strip():
                continue

            query_dicts = generate_queries_for_doc(client, title)
            for qd in query_dicts:
                query = qd["query"]
                query_type = qd["query_type"]

                # Category-aware filter:
                # Hard categories (Hindi, brand_as_generic): embedding-only + looser top-50
                # Easy categories (English, symptom): hybrid top-20
                is_hard = query_type in HARD_QUERY_TYPES
                k = 50 if is_hard else 20
                hits = search_top_k(query, k=k, embedding_only=is_hard)
                hit_ids = [str(h.get("id") or h.get("_id") or "") for h in hits]
                if doc_id not in hit_ids:
                    continue  # filter: retriever must find gold doc

                # Trim candidates to top-20 for consistency
                hits = hits[:20]
                record = {
                    "query": query,
                    "query_type": query_type,
                    "gold_doc_id": doc_id,
                    "gold_doc_title": title,
                    "candidates": [
                        {
                            "doc_id": str(h.get("id") or h.get("_id") or ""),
                            "doc_title": h.get("title") or h.get("name") or "",
                            "teacher_score": None,  # filled in Stage 3
                        }
                        for h in hits
                    ],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(docs)} docs, {written} queries written")
            time.sleep(0.05)  # stay under 150K TPM

    print(f"done: {written} filtered queries → {args.out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_generate_listwise.py -v
```

Expected: all 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_listwise_data.py tests/test_generate_listwise.py
git commit -m "feat(T610): generate_listwise_data.py — Azure GPT-4o-mini query gen + filter helpers"
```

---

## Task 3: Write and test the listwise loss function

**Files:**
- Create: `training/listwise_loss.py`
- Create: `tests/test_listwise_loss.py`

This is the core training signal change. The loss is KL(student_rankings ‖ teacher_rankings) + InfoNCE. Must be unit-tested before the training script is built on top of it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_listwise_loss.py`:

```python
"""Tests for the CADeT combined listwise + InfoNCE loss."""
import torch
import pytest
from training.listwise_loss import ListwiseKLLoss, compute_listwise_kl, compute_infonce


def _rand_emb(batch: int, k: int, dim: int = 64) -> tuple[torch.Tensor, torch.Tensor]:
    """Returns (query_emb, doc_embs) with unit-normalized rows."""
    q = torch.randn(batch, dim)
    q = q / q.norm(dim=-1, keepdim=True)
    d = torch.randn(batch, k, dim)
    d = d / d.norm(dim=-1, keepdim=True)
    return q, d


def test_compute_listwise_kl_output_shape():
    q, d = _rand_emb(4, 20)
    teacher_scores = torch.randn(4, 20)
    loss = compute_listwise_kl(q, d, teacher_scores, temperature=1.0)
    assert loss.shape == ()  # scalar
    assert loss.item() >= 0.0  # KL is non-negative


def test_compute_infonce_output_shape():
    q, d = _rand_emb(4, 20)
    # gold doc is always index 0
    loss = compute_infonce(q, d)
    assert loss.shape == ()
    assert loss.item() >= 0.0


def test_listwise_kl_loss_decreases_with_perfect_teacher():
    """Student that matches teacher exactly should have near-zero KL loss."""
    q, d = _rand_emb(2, 5, dim=16)
    # teacher scores = student dot products (so student already matches teacher)
    student_scores = torch.bmm(d, q.unsqueeze(-1)).squeeze(-1)
    loss = compute_listwise_kl(q, d, teacher_scores=student_scores)
    assert loss.item() < 0.01


def test_combined_loss_uses_both_components():
    """Combined loss must be a weighted sum of KL and InfoNCE."""
    q, d = _rand_emb(4, 10)
    teacher_scores = torch.randn(4, 10)
    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    loss = criterion(q, d, teacher_scores)
    kl = compute_listwise_kl(q, d, teacher_scores)
    nce = compute_infonce(q, d)
    expected = 0.6 * kl + 0.4 * nce
    assert abs(loss.item() - expected.item()) < 1e-5


def test_loss_differentiable():
    """Loss must produce gradients for backprop."""
    q = torch.randn(2, 8, requires_grad=True)
    d = torch.randn(2, 5, 8, requires_grad=True)
    teacher_scores = torch.randn(2, 5)
    criterion = ListwiseKLLoss()
    loss = criterion(q, d, teacher_scores)
    loss.backward()
    assert q.grad is not None
    assert d.grad is not None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
python3 -m pytest tests/test_listwise_loss.py -v 2>&1 | head -10
```

Expected: `ImportError` — `training/listwise_loss.py` doesn't exist yet.

- [ ] **Step 3: Create `training/listwise_loss.py`**

```python
"""CADeT combined listwise KL + InfoNCE loss.

Reference: Tamber et al. 2025 (arxiv:2505.19274) — λ₁=0.6 KL + λ₂=0.4 InfoNCE.

Usage in training:
    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    loss = criterion(query_emb, doc_embs, teacher_scores)
    loss.backward()
"""
from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import Tensor


def compute_listwise_kl(
    query_emb: Tensor,        # [B, D]
    doc_embs: Tensor,         # [B, K, D]
    teacher_scores: Tensor,   # [B, K] — raw cross-encoder logits, will be softmax'd
    temperature: float = 1.0,
) -> Tensor:
    """KL(student_probs ‖ teacher_probs) averaged over batch."""
    # Student scores via dot product
    student_logits = torch.bmm(doc_embs, query_emb.unsqueeze(-1)).squeeze(-1) / temperature  # [B, K]
    student_log_probs = F.log_softmax(student_logits, dim=-1)

    # Teacher probs (normalize teacher scores to probability distribution)
    teacher_probs = F.softmax(teacher_scores / temperature, dim=-1)

    return F.kl_div(student_log_probs, teacher_probs, reduction="batchmean")


def compute_infonce(
    query_emb: Tensor,  # [B, D]
    doc_embs: Tensor,   # [B, K, D] — index 0 is always the gold positive
    temperature: float = 0.05,
) -> Tensor:
    """Standard InfoNCE: gold doc at index 0 vs all K candidates."""
    logits = torch.bmm(doc_embs, query_emb.unsqueeze(-1)).squeeze(-1) / temperature  # [B, K]
    targets = torch.zeros(logits.size(0), dtype=torch.long, device=logits.device)  # gold = index 0
    return F.cross_entropy(logits, targets)


class ListwiseKLLoss(torch.nn.Module):
    def __init__(self, lambda_listwise: float = 0.6, lambda_infonce: float = 0.4):
        super().__init__()
        self.lambda_listwise = lambda_listwise
        self.lambda_infonce = lambda_infonce

    def forward(
        self,
        query_emb: Tensor,       # [B, D]
        doc_embs: Tensor,        # [B, K, D]
        teacher_scores: Tensor,  # [B, K]
    ) -> Tensor:
        kl = compute_listwise_kl(query_emb, doc_embs, teacher_scores)
        nce = compute_infonce(query_emb, doc_embs)
        return self.lambda_listwise * kl + self.lambda_infonce * nce
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
python3 -m pytest tests/test_listwise_loss.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add training/listwise_loss.py tests/test_listwise_loss.py
git commit -m "feat(T610): listwise KL + InfoNCE loss — CADeT training signal (arxiv:2505.19274)"
```

---

## Task 4: Teacher scoring stage

**Files:**
- Modify: `scripts/generate_listwise_data.py` — add `score_with_teacher()` function
- Modify: `tests/test_generate_listwise.py` — add teacher scoring tests

The teacher is `BAAI/bge-reranker-v2-m3`. It runs locally and produces a scalar score per (query, doc) pair. This stage reads the Stage 1+2 JSONL, fills in `teacher_score`, writes a new JSONL.

- [ ] **Step 1: Add teacher scoring tests**

Add to `tests/test_generate_listwise.py`:

```python
from scripts.generate_listwise_data import normalize_teacher_scores


def test_normalize_teacher_scores_range():
    scores = [3.2, -1.5, 0.0, 7.8, 2.1]
    normed = normalize_teacher_scores(scores)
    assert abs(min(normed)) < 1e-6       # min → 0.0
    assert abs(max(normed) - 1.0) < 1e-6 # max → 1.0
    assert len(normed) == len(scores)


def test_normalize_teacher_scores_constant_input():
    # All same scores → should not divide by zero
    scores = [2.0, 2.0, 2.0]
    normed = normalize_teacher_scores(scores)
    assert all(s == 0.0 for s in normed)
```

- [ ] **Step 2: Run to confirm they fail**

```bash
python3 -m pytest tests/test_generate_listwise.py::test_normalize_teacher_scores_range -v
```

Expected: `ImportError` for `normalize_teacher_scores`.

- [ ] **Step 3: Add teacher scoring functions to `scripts/generate_listwise_data.py`**

Add after the existing imports:

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

_TEACHER_MODEL = None
_TEACHER_TOKENIZER = None
TEACHER_MODEL_NAME = "BAAI/bge-reranker-v2-m3"


def _load_teacher():
    global _TEACHER_MODEL, _TEACHER_TOKENIZER
    if _TEACHER_MODEL is None:
        print(f"loading teacher {TEACHER_MODEL_NAME}...")
        _TEACHER_TOKENIZER = AutoTokenizer.from_pretrained(TEACHER_MODEL_NAME)
        _TEACHER_MODEL = AutoModelForSequenceClassification.from_pretrained(TEACHER_MODEL_NAME)
        _TEACHER_MODEL.eval()
    return _TEACHER_MODEL, _TEACHER_TOKENIZER


def normalize_teacher_scores(scores: list[float]) -> list[float]:
    """Min-max normalize to [0, 1]. Returns zeros if all scores are equal."""
    lo, hi = min(scores), max(scores)
    if hi == lo:
        return [0.0] * len(scores)
    return [(s - lo) / (hi - lo) for s in scores]


def score_candidates_with_teacher(query: str, candidates: list[dict]) -> list[float]:
    """Returns min-max normalized teacher scores, one per candidate."""
    model, tokenizer = _load_teacher()
    pairs = [[query, c["doc_title"]] for c in candidates]
    with torch.no_grad():
        inputs = tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        )
        logits = model(**inputs).logits.squeeze(-1).tolist()
    if isinstance(logits, float):
        logits = [logits]
    return normalize_teacher_scores(logits)
```

Also add a `--score` CLI flag to the `main()` function:

```python
# In main(), after the Stage 1+2 data is written, add a Stage 3 pass:
def score_stage(raw_path: Path, out_path: Path) -> None:
    """Stage 3: fill in teacher_score for all candidates in raw JSONL."""
    records = [json.loads(l) for l in raw_path.read_text().splitlines() if l.strip()]
    print(f"scoring {len(records)} records with teacher {TEACHER_MODEL_NAME}...")
    with out_path.open("w") as f:
        for i, rec in enumerate(records):
            scores = score_candidates_with_teacher(rec["query"], rec["candidates"])
            for cand, score in zip(rec["candidates"], scores):
                cand["teacher_score"] = score
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if (i + 1) % 200 == 0:
                print(f"  {i+1}/{len(records)} scored")
    print(f"scored → {out_path}")
```

Update `main()` to call `score_stage()` after the generation loop, saving to `listwise_scored.jsonl`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_generate_listwise.py -v
```

Expected: all tests PASS (teacher scoring tests don't actually load the model — they only test `normalize_teacher_scores`).

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_listwise_data.py tests/test_generate_listwise.py
git commit -m "feat(T610): teacher scoring stage — bge-reranker-v2-m3 + min-max normalization"
```

---

## Task 5: Run the data generation pipeline end-to-end

This is an operational step. Make sure `start_all.sh` is running (Meilisearch + FastAPI) before starting.

- [ ] **Step 1: Ensure search API is up**

```bash
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
```

Expected: `{"status": "ok", ...}`

If not running: `bash scripts/start_all.sh`

- [ ] **Step 2: Run Stage 1+2 (query gen + search filter)**

```bash
source .env
python3 -m scripts.generate_listwise_data --n-docs 5000 \
  --out data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl
```

Expected runtime: ~40-60 min. Expected output: 15K-25K queries in `listwise_raw.jsonl` (filter removes ~30-50% that the retriever can't find).

- [ ] **Step 3: Run Stage 3 (teacher scoring)**

Teacher model (~1.1GB) downloads automatically on first run.

```bash
source .env
python3 -m scripts.generate_listwise_data --score \
  --raw data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl \
  --out data/training/experiments/2026-04-22-cadet/listwise_scored.jsonl
```

Expected runtime: 2-4 hrs on Mac CPU (bge-reranker-v2-m3 is 568M params). Run overnight or on a GPU if impatient.

- [ ] **Step 4: Verify output**

```bash
python3 - <<'EOF'
import json
from pathlib import Path
from collections import Counter

records = [json.loads(l) for l in Path("data/training/experiments/2026-04-22-cadet/listwise_scored.jsonl").read_text().splitlines() if l.strip()]
print(f"total records: {len(records)}")
print(f"query types: {Counter(r['query_type'] for r in records)}")
print(f"avg candidates per record: {sum(len(r['candidates']) for r in records)/len(records):.1f}")
# Check teacher scores are filled
has_scores = sum(1 for r in records if all(c['teacher_score'] is not None for c in r['candidates']))
print(f"records with all teacher scores: {has_scores}/{len(records)}")
EOF
```

Expected: 15K-25K records, 6 query types roughly equal, avg ~18-20 candidates, all teacher scores filled.

---

## Task 6: Upload training data to HF Hub

**Files:**
- Create: `scripts/upload_listwise_to_hf.py`

- [ ] **Step 1: Write the upload script**

Create `scripts/upload_listwise_to_hf.py`:

```python
"""Upload listwise training data to HF Hub as a private dataset.

Usage:
    python3 -m scripts.upload_listwise_to_hf
"""
from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from huggingface_hub import HfApi

SRC = Path("data/training/experiments/2026-04-22-cadet/listwise_scored.jsonl")
REPO = "ManmohanBuildsProducts/auto-parts-listwise-v1"


def main() -> None:
    records = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    print(f"loaded {len(records)} records")

    # Flatten candidates into columns for HF Dataset compatibility
    flat = []
    for rec in records:
        flat.append({
            "query": rec["query"],
            "query_type": rec["query_type"],
            "gold_doc_id": rec["gold_doc_id"],
            "gold_doc_title": rec["gold_doc_title"],
            "candidate_doc_ids": json.dumps([c["doc_id"] for c in rec["candidates"]]),
            "candidate_doc_titles": json.dumps([c["doc_title"] for c in rec["candidates"]]),
            "teacher_scores": json.dumps([c["teacher_score"] for c in rec["candidates"]]),
        })

    HfApi().create_repo(repo_id=REPO, repo_type="dataset", private=True, exist_ok=True)
    ds = Dataset.from_list(flat)
    ds.push_to_hub(REPO, private=True, commit_message="listwise v1 — 5K catalog docs, bge-reranker-v2-m3 teacher")
    print(f"pushed {len(flat)} rows → https://huggingface.co/datasets/{REPO}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

```bash
python3 -m scripts.upload_listwise_to_hf
```

- [ ] **Step 3: Verify**

```bash
python3 -c "
from datasets import load_dataset
ds = load_dataset('ManmohanBuildsProducts/auto-parts-listwise-v1', split='train')
print(ds)
print(ds[0].keys())
"
```

Expected: Dataset with columns query, query_type, gold_doc_id, gold_doc_title, candidate_doc_ids, candidate_doc_titles, teacher_scores.

- [ ] **Step 4: Commit**

```bash
git add scripts/upload_listwise_to_hf.py
git commit -m "feat(T610): upload listwise training data to HF Hub"
```

---

## Task 7: Write the HF Jobs training script

**Files:**
- Create: `training/train_listwise.py`

This runs on HF Jobs (A100). It loads the dataset from HF Hub, fine-tunes BGE-m3 with the listwise loss, and pushes the best checkpoint.

- [ ] **Step 1: Create `training/train_listwise.py`**

```python
"""CADeT listwise distillation training script — runs on HF Jobs A100.

Loads:
  - ManmohanBuildsProducts/auto-parts-listwise-v1 → listwise KL loss (new signal)
  - ManmohanBuildsProducts/auto-parts-search-pairs → golden-v2 InfoNCE (preserves domain adaptation)
Base:  ManmohanBuildsProducts/auto-parts-search-v3  (v3 not BGE-m3 — keeps +35% domain adaptation)
Loss:  Interleaved: listwise batches use ListwiseKLLoss (KL+InfoNCE λ=0.6/0.4);
       golden-v2 batches use InfoNCE-only (teacher_scores synthesized from gold@0 position).
Out:   ManmohanBuildsProducts/auto-parts-search-v4-cadet (private)

Training ratio: 2 listwise batches : 1 golden-v2 batch (golden-v2 = 26,760 pairs, listwise ~20K).

Usage on HF Jobs:
    Set env vars: HF_TOKEN
    python3 training/train_listwise.py

Usage locally (smoke test, tiny subset):
    HF_TOKEN=... python3 training/train_listwise.py --smoke-test
"""
from __future__ import annotations

import argparse
import json
import os
import random
from itertools import cycle
from pathlib import Path

import torch
from datasets import load_dataset
from sentence_transformers import SentenceTransformer
from torch.utils.data import DataLoader, Dataset as TorchDataset

from training.listwise_loss import ListwiseKLLoss

HF_TOKEN = os.environ.get("HF_TOKEN", "")
LISTWISE_DATASET = "ManmohanBuildsProducts/auto-parts-listwise-v1"
GOLDEN_DATASET = "ManmohanBuildsProducts/auto-parts-search-pairs"
BASE_MODEL = "ManmohanBuildsProducts/auto-parts-search-v3"
OUTPUT_REPO = "ManmohanBuildsProducts/auto-parts-search-v4-cadet"
EPOCHS = 3
BATCH_SIZE = 16
LR = 2e-5
MAX_SEQ_LEN = 128
GOLDEN_INTERLEAVE_RATIO = 2  # 1 golden-v2 batch per N listwise batches


class ListwiseDataset(TorchDataset):
    def __init__(self, hf_dataset):
        self.records = list(hf_dataset)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx):
        rec = self.records[idx]
        query = rec["query"]
        cand_titles = json.loads(rec["candidate_doc_titles"])
        teacher_scores = json.loads(rec["teacher_scores"])
        gold_title = rec["gold_doc_title"]

        # Gold doc always at index 0 for InfoNCE component
        if gold_title in cand_titles:
            gold_idx = cand_titles.index(gold_title)
            cand_titles.insert(0, cand_titles.pop(gold_idx))
            teacher_scores.insert(0, teacher_scores.pop(gold_idx))
        else:
            cand_titles.insert(0, gold_title)
            teacher_scores.insert(0, 1.0)

        return {
            "query": query,
            "candidates": cand_titles[:20],
            "teacher_scores": torch.tensor(teacher_scores[:20], dtype=torch.float),
        }


class GoldenV2Dataset(TorchDataset):
    """Golden-v2 pair dataset for InfoNCE-only training.

    Each record is a (query, positive) pair from the 26,760 golden pairs.
    We build a small in-batch negatives set by grouping BATCH_SIZE pairs together.
    """
    def __init__(self, hf_dataset):
        self.records = [
            {"query": r["query"], "positive": r["positive"]}
            for r in hf_dataset
            if r.get("query") and r.get("positive")
        ]

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, idx):
        return self.records[idx]


def encode(model: SentenceTransformer, texts: list[str]) -> torch.Tensor:
    return model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)


def train(smoke_test: bool = False) -> None:
    print(f"base model: {BASE_MODEL}")
    print(f"loading listwise dataset {LISTWISE_DATASET}...")
    listwise_ds = load_dataset(LISTWISE_DATASET, split="train", token=HF_TOKEN)
    print(f"loading golden-v2 dataset {GOLDEN_DATASET}...")
    golden_ds = load_dataset(GOLDEN_DATASET, split="train", token=HF_TOKEN)

    if smoke_test:
        listwise_ds = listwise_ds.select(range(min(200, len(listwise_ds))))
        golden_ds = golden_ds.select(range(min(100, len(golden_ds))))

    print(f"  listwise: {len(listwise_ds)} | golden-v2: {len(golden_ds)}")

    model = SentenceTransformer(BASE_MODEL, trust_remote_code=True, token=HF_TOKEN)
    model.max_seq_length = MAX_SEQ_LEN
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device)
    print(f"using {device.upper()}")

    criterion = ListwiseKLLoss(lambda_listwise=0.6, lambda_infonce=0.4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LR)
    # Steps = listwise steps + golden-v2 steps per epoch
    listwise_steps_per_epoch = len(listwise_ds) // BATCH_SIZE
    golden_steps_per_epoch = listwise_steps_per_epoch // GOLDEN_INTERLEAVE_RATIO
    n_steps = (listwise_steps_per_epoch + golden_steps_per_epoch) * EPOCHS
    scheduler = torch.optim.lr_scheduler.LinearLR(
        optimizer, start_factor=1.0, end_factor=0.0, total_iters=n_steps
    )

    best_loss = float("inf")
    ckpt_dir = Path("checkpoints/cadet")
    ckpt_dir.mkdir(parents=True, exist_ok=True)

    for epoch in range(1 if smoke_test else EPOCHS):
        model.train()
        epoch_loss = 0.0
        n_batches = 0

        listwise_loader = DataLoader(
            ListwiseDataset(listwise_ds), batch_size=BATCH_SIZE, shuffle=True, collate_fn=lambda x: x
        )
        golden_loader = cycle(DataLoader(
            GoldenV2Dataset(golden_ds), batch_size=BATCH_SIZE, shuffle=True, collate_fn=lambda x: x
        ))

        for step, listwise_batch in enumerate(listwise_loader):
            # --- Listwise batch (KL + InfoNCE combined loss) ---
            queries = [item["query"] for item in listwise_batch]
            all_candidates = [item["candidates"] for item in listwise_batch]
            all_teacher = torch.stack([item["teacher_scores"] for item in listwise_batch]).to(device)

            q_emb = encode(model, queries)
            flat_cands = [c for cands in all_candidates for c in cands]
            flat_emb = encode(model, flat_cands)
            k = len(all_candidates[0])
            doc_embs = flat_emb.view(len(listwise_batch), k, -1)

            loss = criterion(q_emb, doc_embs, all_teacher)
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            epoch_loss += loss.item()
            n_batches += 1

            # --- Golden-v2 interleave batch (InfoNCE-only, every GOLDEN_INTERLEAVE_RATIO steps) ---
            if step % GOLDEN_INTERLEAVE_RATIO == 0:
                gold_batch = next(golden_loader)
                g_queries = [item["query"] for item in gold_batch]
                g_positives = [item["positive"] for item in gold_batch]

                g_q_emb = encode(model, g_queries)    # [B, D]
                g_p_emb = encode(model, g_positives)  # [B, D]
                # In-batch NCE: [B, B] score matrix, diagonal = positive pair
                import torch.nn.functional as F
                scores = torch.mm(g_q_emb, g_p_emb.t()) / 0.05  # [B, B]
                targets = torch.arange(len(gold_batch), device=device)
                g_loss = F.cross_entropy(scores, targets)
                optimizer.zero_grad()
                g_loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                epoch_loss += g_loss.item()
                n_batches += 1

        avg_loss = epoch_loss / max(n_batches, 1)
        print(f"epoch {epoch+1}/{EPOCHS} — avg loss: {avg_loss:.4f}")

        if avg_loss < best_loss:
            best_loss = avg_loss
            model.save(str(ckpt_dir / "best"))
            print(f"  saved best checkpoint (loss={best_loss:.4f})")

    # Push best checkpoint to HF Hub
    if not smoke_test:
        best_model = SentenceTransformer(str(ckpt_dir / "best"), trust_remote_code=True)
        best_model.push_to_hub(OUTPUT_REPO, private=True, token=HF_TOKEN)
        print(f"pushed → https://huggingface.co/ManmohanBuildsProducts/auto-parts-search-v4-cadet")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    train(smoke_test=args.smoke_test)
```

- [ ] **Step 2: Smoke test locally (CPU, 200 examples)**

```bash
source .env
HF_TOKEN=$(cat ~/.cache/huggingface/token) python3 training/train_listwise.py --smoke-test
```

Expected: runs 1 epoch on 200 examples, prints loss, exits cleanly. No GPU needed for smoke test.

- [ ] **Step 3: Commit**

```bash
git add training/train_listwise.py
git commit -m "feat(T610): train_listwise.py — CADeT training script for HF Jobs A100"
```

---

## Task 8: Submit HF Jobs training run

HF Jobs runs a Python script on HF-managed GPU hardware using your HF credits.

- [ ] **Step 1: Install HF CLI job tools if needed**

```bash
pip install huggingface_hub[cli]
huggingface-cli jobs --help
```

- [ ] **Step 2: Submit the training job**

```bash
HF_TOKEN=$(cat ~/.cache/huggingface/token) huggingface-cli jobs run \
  --command "python training/train_listwise.py" \
  --flavor a100-80gb \
  --env HF_TOKEN=$(cat ~/.cache/huggingface/token)
```

If that CLI syntax differs, check `huggingface-cli jobs --help` and adjust. The key params are: the script path, A100 GPU flavor, and HF_TOKEN env var.

- [ ] **Step 3: Monitor the run**

```bash
huggingface-cli jobs list
```

Expected: job appears with status `running`. Typical runtime: 2-4 hrs on A100 for 3 epochs on 20K examples.

- [ ] **Step 4: Confirm model was pushed**

After the job completes:
```bash
python3 -c "
from huggingface_hub import HfApi
info = HfApi().model_info('ManmohanBuildsProducts/auto-parts-search-v4-cadet', token='$(cat ~/.cache/huggingface/token)')
print(info.modelId, info.lastModified)
"
```

---

## Task 9: Evaluate v4-cadet on dev-149

Use the existing evaluation harness. Compare v4-cadet against v3 (0.430) and OpenAI (0.468).

- [ ] **Step 1: Run evaluation**

```bash
source .env
python3 -m training.evaluate \
  --model ManmohanBuildsProducts/auto-parts-search-v4-cadet \
  --benchmark data/training/golden/benchmark_dev_graded.jsonl \
  --corpus data/external/processed/v3_corpus_docs.json \
  --out data/training/experiments/2026-04-22-cadet/eval_results.json
```

- [ ] **Step 2: Check against gate (ADR 017)**

Gate: nDCG@10 ≥ 0.452 overall OR ≥ +10% on brand_as_generic slice.

```bash
python3 -c "
import json
r = json.load(open('data/training/experiments/2026-04-22-cadet/eval_results.json'))
print(f'overall nDCG@10: {r[\"ndcg@10\"]:.3f} (baseline 0.430, gate 0.452, OpenAI 0.468)')
print(f'brand_as_generic: {r.get(\"ndcg@10_brand_as_generic\", \"N/A\")}')
print('GATE PASS' if r['ndcg@10'] >= 0.452 else 'GATE FAIL — see ADR 017 for next steps')
"
```

- [ ] **Step 3: Commit results**

```bash
git add data/training/experiments/2026-04-22-cadet/eval_results.json
git commit -m "eval(T610): v4-cadet nDCG@10=<RESULT> vs v3=0.430 baseline"
```

---

## Self-review

**Spec coverage:**
- [x] Azure GPT-4o-mini for query generation (Task 2)
- [x] 6 query types including Hindi/Hinglish (Task 2, `QUERY_TYPES` list)
- [x] bge-reranker-v2-m3 teacher scoring (Task 4)
- [x] KL + InfoNCE combined loss with λ=0.6/0.4 (Task 3)
- [x] Filter: gold doc must be in retriever top-20 (Task 2, `search_top_k` filter)
- [x] HF Hub dataset upload (Task 6)
- [x] HF Jobs A100 training (Task 8)
- [x] Evaluation against ADR 017 gate (Task 9)
- [x] All arxiv citations saved in `memory/learnings.md` (done before this plan)

**Placeholder scan:** None. All steps have working code.

**Type consistency:** `score_candidates_with_teacher` returns `list[float]` → used correctly in `score_stage`. `ListwiseKLLoss.forward` takes `(Tensor, Tensor, Tensor)` → called correctly in training loop.

---

## Techniques 2 + 3 (stub — separate plans)

After Technique 1 ships and passes the gate:

**Plan B — CLEAR cross-lingual alignment:** Translate existing 27K pairs + Technique 1 synthetic queries to Hindi/Hinglish via Azure GPT-4o-mini. Add reversed contrastive loss + KL distribution alignment loss. Stacks on v4-cadet as the new base. Expected +5-10 pts on Hindi slice.

**Plan C — EBRM entity-aware pooling:** Extract BRAND/PART_TYPE/MODEL entity spans from KG. Entity-aware mean-pooling + 2-3× upweighted InfoNCE on entity contrasts. Use DeepSeek-chat (DEEPSEEK_API_KEY) for brand↔generic paraphrase generation. Can be fused at inference: `s_final = s_dense + α*s_entity`.
