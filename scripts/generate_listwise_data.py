"""CADeT-style listwise training data generation.

Stage 1: Generate 6 synthetic query types per catalog passage (Azure GPT-4o-mini).
Stage 2: Filter — our hybrid search must return the source doc in top-20.
Stage 3: Score top-20 candidates with bge-reranker-v2-m3 (local cross-encoder teacher).

Output: JSONL of {query, query_type, gold_doc_id, candidates: [{doc_id, doc_text, teacher_score}]}

Usage:
    source .env
    python3.11 -m scripts.generate_listwise_data --n-docs 5000 --out data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl
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
MEILI_URL = os.environ.get("MEILI_URL", "http://127.0.0.1:7700")
MEILI_KEY = os.environ.get("MEILI_KEY", "aps_local_dev_key_do_not_use_in_prod")
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
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        queries = json.loads(raw[start : end + 1])
        if not isinstance(queries, list):
            return []
        clean = [q.strip() for q in queries if isinstance(q, str) and q.strip()]
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

# Query types where BM25 actively hurts recall — use embedding-only + looser top-50 filter
HARD_QUERY_TYPES = {"hindi_natural", "hinglish", "romanized_hindi", "brand_generic_variant"}


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
        return [
            {"query": q, "query_type": QUERY_TYPES[i] if i < len(QUERY_TYPES) else "other"}
            for i, q in enumerate(queries)
        ]
    except Exception:
        return []


def search_top_k(query: str, k: int = 20, embedding_only: bool = False) -> list[dict]:
    """Hit the local /search endpoint and return top-k hits.

    embedding_only is unused — the API auto-classifies queries and applies appropriate
    BM25/embedding weights (Hindi queries already get embedding-heavy routing).
    k capped at 50 (API max).
    """
    try:
        r = requests.get(f"{SEARCH_API}/search", params={"q": query, "k": min(k, 50)}, timeout=10)
        r.raise_for_status()
        return r.json().get("hits", [])
    except Exception:
        return []


def fetch_catalog_docs_stratified(n_docs: int) -> list[dict]:
    """γ-strategy-biased doc sampling.

    Target split: ~40% eauto, ~35% spareshub, ~15% bikespares, ~10% rest.
    """
    meili = f"{MEILI_URL}/indexes/parts/search"
    headers = {"Authorization": f"Bearer {MEILI_KEY}", "Content-Type": "application/json"}

    def fetch_source(source: str, limit: int) -> list[dict]:
        r = requests.post(meili, json={"q": "", "limit": limit, "filter": f"source = '{source}' AND doc_type = 'catalog'"}, headers=headers)
        r.raise_for_status()
        return r.json()["hits"]

    random.seed(SEED)
    eauto = random.sample(fetch_source("eauto", 10000), min(int(n_docs * 0.40), 2000))
    spareshub = random.sample(fetch_source("spareshub", 15000), min(int(n_docs * 0.35), 1750))
    bikespares = random.sample(fetch_source("bikespares", 3000), min(int(n_docs * 0.15), 750))

    remainder_n = n_docs - len(eauto) - len(spareshub) - len(bikespares)
    all_rest = requests.post(meili, json={"q": "", "limit": 5000, "filter": "doc_type = 'catalog'"}, headers=headers).json()["hits"]
    sampled_ids = {str(d.get("id") or d.get("_id")) for d in eauto + spareshub + bikespares}
    rest = [d for d in all_rest if str(d.get("id") or d.get("_id")) not in sampled_ids]
    rest = random.sample(rest, min(remainder_n, len(rest)))

    docs = eauto + spareshub + bikespares + rest
    print(f"stratified sample: {len(eauto)} eauto + {len(spareshub)} spareshub + "
          f"{len(bikespares)} bikespares + {len(rest)} rest = {len(docs)} total")
    return docs


# --- Teacher scoring ---

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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-docs", type=int, default=5000)
    parser.add_argument("--out", type=Path, default=Path("data/training/experiments/2026-04-22-cadet/listwise_raw.jsonl"))
    parser.add_argument("--score", action="store_true", help="Run Stage 3 (teacher scoring) instead of Stage 1+2")
    parser.add_argument("--raw", type=Path, help="Input JSONL for --score stage")
    args = parser.parse_args()

    if args.score:
        raw = args.raw or args.out.parent / "listwise_raw.jsonl"
        out = args.out.parent / "listwise_scored.jsonl"
        score_stage(raw, out)
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    client = make_azure_client()

    print("fetching catalog docs from Meilisearch (γ-biased stratified sample)...")
    docs = fetch_catalog_docs_stratified(args.n_docs)

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
            title = doc.get("name") or doc.get("title") or ""
            if not title.strip():
                continue

            query_dicts = generate_queries_for_doc(client, title)
            for qd in query_dicts:
                query = qd["query"]
                query_type = qd["query_type"]

                is_hard = query_type in HARD_QUERY_TYPES
                k = 50 if is_hard else 20
                hits = search_top_k(query, k=k, embedding_only=is_hard)
                # API returns part_id as the doc identifier
                hit_ids = [str(h.get("part_id") or h.get("id") or "") for h in hits]
                if doc_id not in hit_ids:
                    continue

                hits = hits[:20]
                record = {
                    "query": query,
                    "query_type": query_type,
                    "gold_doc_id": doc_id,
                    "gold_doc_title": title,
                    "candidates": [
                        {
                            "doc_id": str(h.get("part_id") or h.get("id") or ""),
                            "doc_title": h.get("name") or "",
                            "teacher_score": None,
                        }
                        for h in hits
                    ],
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                written += 1

            if (i + 1) % 100 == 0:
                print(f"  {i+1}/{len(docs)} docs, {written} queries written")
            time.sleep(0.05)

    print(f"done: {written} filtered queries → {args.out}")


if __name__ == "__main__":
    main()
