"""Unified embedder for T305 external benchmark.

Handles 6 models with their distinct prefix / input_type / task conventions.
Disk-caches embeddings per (model_key, role) as .npy to avoid re-spending on
API calls or re-running local inference across bench rounds.

Usage:
    from scripts._embed_api import embed, MODELS
    doc_emb   = embed("openai-3-large", docs, role="doc")
    query_emb = embed("openai-3-large", queries, role="query")
"""
from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Literal

import numpy as np

Role = Literal["query", "doc"]

CACHE_DIR = Path("data/external/processed/bench_round1")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Per-model config. The KEY becomes the row label in the final table.
# Each entry: provider, model_id, dim, query_prefix/doc_prefix OR input_type/task.
MODELS: dict[str, dict] = {
    "openai-3-large": {
        "provider": "openai",
        "model_id": "text-embedding-3-large",
        "dim": 3072,
        # OpenAI: no prefix, no input_type.
    },
    "cohere-mult-v3": {
        "provider": "cohere",
        "model_id": "embed-multilingual-v3.0",
        "dim": 1024,
        "input_type_query": "search_query",
        "input_type_doc": "search_document",
    },
    "jina-v3": {
        "provider": "jina",
        "model_id": "jina-embeddings-v3",
        "dim": 1024,
        "task_query": "retrieval.query",
        "task_doc": "retrieval.passage",
    },
    "e5-large": {
        "provider": "hf_local",
        "model_id": "intfloat/multilingual-e5-large",
        "dim": 1024,
        "query_prefix": "query: ",
        "doc_prefix": "passage: ",
    },
    "bge-m3": {
        "provider": "hf_local",
        "model_id": "BAAI/bge-m3",
        "dim": 1024,
        # BGE-m3 dense: no prefix.
    },
    "v3-ours": {
        "provider": "hf_local",
        "model_id": "ManmohanBuildsProducts/auto-parts-search-v3",
        "dim": 1024,
        # v3 fine-tuned with no prefix (verified via search_hybrid.py).
    },
}


# ---------- cache ----------

def _cache_path(model_key: str, role: Role, texts_hash: str) -> Path:
    return CACHE_DIR / f"{model_key}__{role}__{texts_hash}.npy"


def _hash_texts(texts: list[str]) -> str:
    h = hashlib.md5()
    h.update(str(len(texts)).encode())
    # Hash first + last 5 and total chars — robust + collision-safe enough
    for t in texts[:5]:
        h.update(t.encode("utf-8", errors="ignore"))
    for t in texts[-5:]:
        h.update(t.encode("utf-8", errors="ignore"))
    h.update(str(sum(len(t) for t in texts)).encode())
    return h.hexdigest()[:12]


# ---------- API backends ----------

def _embed_openai(texts: list[str], model_id: str, role: Role) -> np.ndarray:
    import requests
    key = os.environ["OPENAI_API_KEY"]
    url = "https://api.openai.com/v1/embeddings"
    out: list[list[float]] = []
    batch_size = 256  # OpenAI allows up to 2048 but token cap can hit
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(4):
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json={"model": model_id, "input": batch},
                timeout=120,
            )
            if r.status_code == 200:
                out.extend([d["embedding"] for d in r.json()["data"]])
                break
            wait = 2 ** attempt
            print(f"  openai batch {i}: status={r.status_code} retry in {wait}s  {r.text[:200]}")
            time.sleep(wait)
        else:
            raise RuntimeError(f"openai batch {i} failed after 4 retries")
        print(f"  openai {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
    return np.asarray(out, dtype=np.float32)


def _embed_cohere(texts: list[str], model_id: str, role: Role) -> np.ndarray:
    import requests
    key = os.environ["COHERE_API_KEY"]
    url = "https://api.cohere.com/v2/embed"
    input_type = "search_query" if role == "query" else "search_document"
    out: list[list[float]] = []
    batch_size = 96  # Cohere cap
    # Trial key: 100K tokens/min. With ~30 tok/doc × 96 = ~2880 tok/batch, cap ≈ 34/min → pace ≥ 1.8s/batch.
    min_batch_interval = 2.0
    last_t = 0.0
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        # Throttle
        dt = time.time() - last_t
        if dt < min_batch_interval:
            time.sleep(min_batch_interval - dt)
        for attempt in range(6):
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model_id,
                    "texts": batch,
                    "input_type": input_type,
                    "embedding_types": ["float"],
                },
                timeout=120,
            )
            last_t = time.time()
            if r.status_code == 200:
                out.extend(r.json()["embeddings"]["float"])
                break
            # Rate limit — wait a full minute (window reset)
            if r.status_code == 429:
                wait = 65
            else:
                wait = 2 ** attempt
            print(f"  cohere batch {i}: status={r.status_code} retry in {wait}s  {r.text[:160]}")
            time.sleep(wait)
        else:
            raise RuntimeError(f"cohere batch {i} failed after 6 retries")
        print(f"  cohere {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
    return np.asarray(out, dtype=np.float32)


def _embed_jina(texts: list[str], model_id: str, role: Role) -> np.ndarray:
    import requests
    key = os.environ["JINA_API_KEY"]
    url = "https://api.jina.ai/v1/embeddings"
    task = "retrieval.query" if role == "query" else "retrieval.passage"
    out: list[list[float]] = []
    batch_size = 64  # smaller to stay well under 100K/min cap
    # Free tier: 100K tokens/min. ~30 tok/doc × 64 = ~1920 tok/batch → pace ≥ 1.2s/batch.
    min_batch_interval = 2.0
    last_t = 0.0
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        dt = time.time() - last_t
        if dt < min_batch_interval:
            time.sleep(min_batch_interval - dt)
        for attempt in range(6):
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model_id,
                    "task": task,
                    "input": batch,
                },
                timeout=180,
            )
            last_t = time.time()
            if r.status_code == 200:
                out.extend([d["embedding"] for d in r.json()["data"]])
                break
            if r.status_code == 429:
                wait = 65
            else:
                wait = 2 ** attempt
            print(f"  jina batch {i}: status={r.status_code} retry in {wait}s  {r.text[:160]}")
            time.sleep(wait)
        else:
            raise RuntimeError(f"jina batch {i} failed after 6 retries")
        print(f"  jina {min(i + batch_size, len(texts))}/{len(texts)}", flush=True)
    return np.asarray(out, dtype=np.float32)


# ---------- local backend ----------

_st_cache: dict = {}


def _embed_hf_local(texts: list[str], model_id: str, role: Role, cfg: dict) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    if model_id not in _st_cache:
        _st_cache[model_id] = SentenceTransformer(model_id, trust_remote_code=True)
    m = _st_cache[model_id]
    prefix = cfg.get("query_prefix" if role == "query" else "doc_prefix", "")
    prefixed = [prefix + t for t in texts] if prefix else texts
    emb = m.encode(prefixed, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True, batch_size=32)
    return emb.astype(np.float32)


# ---------- unified entry ----------

def embed(model_key: str, texts: list[str], role: Role, use_cache: bool = True) -> np.ndarray:
    if model_key not in MODELS:
        raise ValueError(f"unknown model: {model_key}. Options: {list(MODELS)}")
    cfg = MODELS[model_key]
    texts_hash = _hash_texts(texts)
    cache_path = _cache_path(model_key, role, texts_hash)

    if use_cache and cache_path.exists():
        emb = np.load(cache_path)
        if emb.shape[0] == len(texts):
            print(f"  [cache hit] {model_key}/{role} -> {emb.shape}  ({cache_path.name})")
            return emb
        print(f"  [cache stale] {model_key}/{role} n={emb.shape[0]} expected={len(texts)}, re-embedding")

    print(f"  [embedding] {model_key}/{role} n={len(texts)} via {cfg['provider']}")
    t0 = time.time()
    prov = cfg["provider"]
    if prov == "openai":
        emb = _embed_openai(texts, cfg["model_id"], role)
    elif prov == "cohere":
        emb = _embed_cohere(texts, cfg["model_id"], role)
    elif prov == "jina":
        emb = _embed_jina(texts, cfg["model_id"], role)
    elif prov == "hf_local":
        emb = _embed_hf_local(texts, cfg["model_id"], role, cfg)
    else:
        raise ValueError(prov)

    # Normalize (cosine = dot on normalized) — OpenAI/Cohere/Jina return unnormalized
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    emb = emb / norms

    np.save(cache_path, emb)
    print(f"  [saved] {model_key}/{role} {emb.shape} in {time.time()-t0:.1f}s -> {cache_path.name}")
    return emb


if __name__ == "__main__":
    # Smoke test: 1 tiny batch per provider
    from dotenv import load_dotenv
    load_dotenv()
    for mk in MODELS:
        print(f"\n--- {mk} ---")
        q = embed(mk, ["brake pad for Swift"], role="query", use_cache=False)
        d = embed(mk, ["Brake Pad Assembly, Front Left"], role="doc", use_cache=False)
        sim = float((q @ d.T)[0, 0])
        print(f"  sim(brake pad query, brake pad doc) = {sim:.3f}  dim={q.shape[1]}")
