"""Per-session demo tenant: upload catalog -> embed -> scoped search.

Holds in-memory session state keyed by a random session_id:
  {
    sid: {
      "name": str,
      "created_at": iso,
      "expires_at": iso,
      "meili_index": str,
      "embeddings": np.ndarray,   # (N, 1024) normalized
      "product_ids": [str, ...],
      "product_names": [str, ...],
      "product_raw": [dict, ...], # hydration for response
    }
  }

Sessions auto-expire after TTL (default 24h). Expiry is opportunistic
(checked on each new upload). Restart loses all sessions — fine for a
demo layer; prospects are told this upfront.

A hard cap (MAX_SESSIONS) bounds memory. LRU eviction when full.

Uses the same v3 embedding model as the main pipeline and the same
tokenizer/BM25 logic for class-weighted RRF.
"""
from __future__ import annotations

import re
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import requests

from auto_parts_search.query_classifier import classify
from auto_parts_search.search_bm25 import MEILI_URL, _headers
from auto_parts_search.search_hybrid import _encode_query, rrf_fuse
from auto_parts_search.tokenizer import IndicTokenizer

TTL_HOURS = 24
MAX_SESSIONS = 8
MAX_PRODUCTS_PER_UPLOAD = 10_000

_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}
_tokenizer = IndicTokenizer()


# ---------- session ID ----------

def _new_sid() -> str:
    # short, URL-safe, readable
    return "d_" + secrets.token_hex(5)


# ---------- evict expired / LRU ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _evict_expired() -> int:
    now = _now()
    dead = [sid for sid, s in _sessions.items()
            if datetime.fromisoformat(s["expires_at"]) < now]
    for sid in dead:
        _drop_session(sid)
    return len(dead)


def _evict_lru_if_full() -> None:
    if len(_sessions) < MAX_SESSIONS:
        return
    oldest = min(_sessions.items(), key=lambda kv: kv[1]["created_at"])[0]
    _drop_session(oldest)


def _drop_session(sid: str) -> None:
    sess = _sessions.pop(sid, None)
    if not sess:
        return
    # Drop Meilisearch index
    try:
        requests.delete(
            f"{MEILI_URL}/indexes/{sess['meili_index']}",
            headers=_headers(), timeout=10,
        )
    except Exception:
        pass


# ---------- Meilisearch index per session ----------

def _meili_create_index(name: str) -> None:
    requests.post(f"{MEILI_URL}/indexes", headers=_headers(),
                  json={"uid": name, "primaryKey": "id"}, timeout=30).raise_for_status()
    # wait a moment for the index task to settle (quick path; not ideal but OK at demo scale)
    time.sleep(0.3)
    requests.patch(f"{MEILI_URL}/indexes/{name}/settings", headers=_headers(), json={
        "searchableAttributes": [
            "name", "aliases", "indexed_tokens", "brand", "vehicle_make", "vehicle_model", "part_numbers",
        ],
        "displayedAttributes": [
            "id", "part_id", "name", "brand", "vehicle_make", "vehicle_model", "part_numbers",
        ],
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 7}},
        "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
    }, timeout=30).raise_for_status()


def _meili_upsert_docs(name: str, docs: list[dict]) -> None:
    # Push in 5K batches; wait for last task
    BATCH = 5000
    last_uid = None
    for i in range(0, len(docs), BATCH):
        chunk = docs[i : i + BATCH]
        t = requests.post(
            f"{MEILI_URL}/indexes/{name}/documents",
            headers=_headers(), json=chunk, timeout=120,
        )
        t.raise_for_status()
        last_uid = t.json()["taskUid"]
    # Wait for last task
    for _ in range(600):
        r = requests.get(f"{MEILI_URL}/tasks/{last_uid}", headers=_headers(), timeout=15)
        r.raise_for_status()
        status = r.json().get("status")
        if status == "succeeded":
            return
        if status == "failed":
            raise RuntimeError(r.json().get("error"))
        time.sleep(0.3)
    raise RuntimeError("ingest task timed out")


def _meili_search(index_name: str, query_str: str, k: int) -> list[dict]:
    r = requests.post(
        f"{MEILI_URL}/indexes/{index_name}/search",
        headers=_headers(),
        json={
            "q": query_str,
            "limit": k,
            "matchingStrategy": "frequency",
            "showRankingScore": True,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("hits", [])


# ---------- part-number extraction (same rules as bulk ingest) ----------

_PART_NUMBER_RE = re.compile(r"\b([A-Z0-9][A-Z0-9-]{4,})\b")
_PN_STOPWORDS = {
    "FRONT", "REAR", "LEFT", "RIGHT", "UPPER", "LOWER", "GENUINE", "COMPLETE",
    "ASSEMBLY", "OEM",
}


def _extract_part_numbers(text: str) -> list[str]:
    out = []
    for m in _PART_NUMBER_RE.findall(text or ""):
        if m.upper() in _PN_STOPWORDS:
            continue
        if not any(c.isdigit() for c in m):
            continue
        if not any(c.isalpha() for c in m) and len(m) < 7:
            continue
        out.append(m)
    return out[:3]


# ---------- public API ----------

@dataclass
class Catalog:
    name: str | None
    products: list[dict]


def upload_catalog(name: str | None, products: list[dict]) -> dict[str, Any]:
    """Create a session from an uploaded catalog. Returns session metadata."""
    if not isinstance(products, list) or not products:
        raise ValueError("products must be a non-empty list")
    if len(products) > MAX_PRODUCTS_PER_UPLOAD:
        raise ValueError(f"too many products: max {MAX_PRODUCTS_PER_UPLOAD}")
    # Validate minimal schema: each item must have at least a name
    for i, p in enumerate(products):
        if not isinstance(p, dict) or not p.get("name"):
            raise ValueError(f"product {i} missing 'name' field")

    with _lock:
        _evict_expired()
        _evict_lru_if_full()

    sid = _new_sid()
    index_name = f"demo_{sid}"

    # Build docs with token expansion + part-number extraction
    docs = []
    product_ids: list[str] = []
    product_names: list[str] = []
    raw_keep: list[dict] = []
    encode_inputs: list[str] = []

    for i, p in enumerate(products):
        pid = str(p.get("id") or f"{sid}_{i}")
        pid = re.sub(r"[^a-zA-Z0-9_-]", "_", pid)[:200]
        name_ = str(p["name"]).strip()
        brand = str(p.get("brand") or "").strip()
        vmake = str(p.get("vehicle_make") or p.get("make") or "").strip()
        vmodel = str(p.get("vehicle_model") or p.get("model") or "").strip()
        description = str(p.get("description") or "").strip()

        # For embedding: same doc style as KG corpus (name + aliases + system)
        emb_text = name_
        if brand: emb_text += f" | brand: {brand}"
        if vmake or vmodel: emb_text += f" | vehicle: {vmake} {vmodel}".strip()
        if description and len(description) < 200:
            emb_text += f" | {description}"

        blob_for_bm25 = " ".join(filter(None, [name_, brand, vmake, vmodel, description]))
        tokens = _tokenizer.index_tokens(blob_for_bm25)
        part_numbers = _extract_part_numbers(name_)

        docs.append({
            "id": pid,
            "part_id": pid,
            "name": name_,
            "brand": brand,
            "vehicle_make": vmake,
            "vehicle_model": vmodel,
            "description": description,
            "indexed_tokens": tokens,
            "part_numbers": part_numbers,
            "aliases": [],  # schema compat
        })
        product_ids.append(pid)
        product_names.append(name_)
        raw_keep.append({
            "id": pid, "name": name_, "brand": brand,
            "vehicle_make": vmake, "vehicle_model": vmodel,
            "part_numbers": part_numbers,
        })
        encode_inputs.append(emb_text)

    # Create Meilisearch index + push docs
    _meili_create_index(index_name)
    _meili_upsert_docs(index_name, docs)

    # Embed via v3 (uses cached model in search_hybrid)
    from sentence_transformers import SentenceTransformer
    from auto_parts_search.search_hybrid import _model_cache, MODEL_NAME
    if MODEL_NAME not in _model_cache:
        _model_cache[MODEL_NAME] = SentenceTransformer(MODEL_NAME, trust_remote_code=True)
    model = _model_cache[MODEL_NAME]
    t0 = time.perf_counter()
    emb = model.encode(
        encode_inputs,
        convert_to_numpy=True,
        normalize_embeddings=True,
        batch_size=32,
        show_progress_bar=False,
    ).astype(np.float32)
    emb_dt = time.perf_counter() - t0

    created_at = _now()
    expires_at = created_at + timedelta(hours=TTL_HOURS)
    session = {
        "id": sid,
        "name": name or "demo",
        "created_at": created_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "meili_index": index_name,
        "embeddings": emb,
        "product_ids": product_ids,
        "product_names": product_names,
        "product_raw": raw_keep,
        "embed_seconds": round(emb_dt, 2),
    }
    with _lock:
        _sessions[sid] = session

    return {
        "session_id": sid,
        "name": session["name"],
        "products_received": len(products),
        "products_embedded": len(products),
        "embedding_seconds": session["embed_seconds"],
        "created_at": session["created_at"],
        "expires_at": session["expires_at"],
        "search_url": f"/demo/{sid}/search",
        "status_url": f"/demo/{sid}",
    }


def get_session(sid: str) -> dict | None:
    return _sessions.get(sid)


def session_summary(sid: str) -> dict | None:
    s = _sessions.get(sid)
    if not s:
        return None
    return {
        "session_id": sid,
        "name": s["name"],
        "n_products": len(s["product_ids"]),
        "created_at": s["created_at"],
        "expires_at": s["expires_at"],
        "sample": s["product_raw"][:5],
    }


def search_in_session(sid: str, query: str, k: int = 10, k_candidates: int = 30) -> dict:
    s = _sessions.get(sid)
    if not s:
        raise KeyError(f"session {sid} not found or expired")

    cls = classify(query)

    # BM25 over this session's Meilisearch index
    q_tokens = _tokenizer.query_tokens(query)
    q_str = " ".join(q_tokens)
    meili_hits = _meili_search(s["meili_index"], q_str, k_candidates)
    bm25_ranks = {h["id"]: i + 1 for i, h in enumerate(meili_hits)}
    id_to_hit = {h["id"]: h for h in meili_hits}

    # Embedding search over this session's embeddings
    q_emb = _encode_query(query)
    scores = s["embeddings"] @ q_emb  # cosine since normalized
    top_idx = np.argsort(-scores)[:k_candidates]
    emb_ranks = {s["product_ids"][i]: rank + 1 for rank, i in enumerate(top_idx)}

    fused = rrf_fuse(bm25_ranks, emb_ranks, cls.bm25_weight, cls.embedding_weight)[:k]

    id_to_raw = {p["id"]: p for p in s["product_raw"]}
    results = []
    for pid, score in fused:
        raw = id_to_raw.get(pid)
        meili_hit = id_to_hit.get(pid, {})
        results.append({
            "part_id": pid,
            "name": (raw or meili_hit).get("name", ""),
            "brand": (raw or meili_hit).get("brand", ""),
            "vehicle_make": (raw or meili_hit).get("vehicle_make", ""),
            "vehicle_model": (raw or meili_hit).get("vehicle_model", ""),
            "part_numbers": (raw or meili_hit).get("part_numbers", []),
            "fused_score": round(float(score), 6),
            "bm25_rank": bm25_ranks.get(pid),
            "embedding_rank": emb_ranks.get(pid),
        })
    return {
        "query": query,
        "query_class": cls.query_class,
        "weights": {"bm25": cls.bm25_weight, "embedding": cls.embedding_weight},
        "classification_reason": cls.evidence,
        "hits": results,
        "session_id": sid,
    }


def delete_session(sid: str) -> bool:
    with _lock:
        if sid in _sessions:
            _drop_session(sid)
            return True
    return False


def list_sessions() -> list[dict]:
    return [
        {
            "session_id": sid,
            "name": s["name"],
            "n_products": len(s["product_ids"]),
            "created_at": s["created_at"],
            "expires_at": s["expires_at"],
        }
        for sid, s in _sessions.items()
    ]
