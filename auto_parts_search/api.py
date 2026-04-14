"""FastAPI /search endpoint — wraps the hybrid BM25+v3 retrieval pipeline.

Run locally:
    uvicorn auto_parts_search.api:app --reload --port 8000

Endpoints:
    GET  /              — service info
    GET  /health        — liveness + backend probes (meili, v3 cache, bridges)
    GET  /classify      — debug: classify a query without searching
    POST /search        — hybrid retrieval
    GET  /search        — same (URL-query variant for curl/browser demos)
    GET  /stats         — bridge + corpus stats

CORS enabled (all origins) for browser demos.
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from auto_parts_search.query_classifier import classify
from auto_parts_search.search_hybrid import (
    _load_corpus_cache,
    EMB_PATH,
    IDS_PATH,
    search as hybrid_search,
)
from auto_parts_search.search_bm25 import MEILI_URL, _meili, INDEX_NAME
from auto_parts_search.tokenizer import bridge_stats
from auto_parts_search import demo_tenant
import requests


# ---------- lifespan: warm caches on startup ----------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm the v3 corpus cache (lazy otherwise); emits helpful logs
    if EMB_PATH.exists():
        _load_corpus_cache()
        print(f"[api] v3 corpus cache warm: {EMB_PATH}")
    else:
        print(f"[api] WARNING: {EMB_PATH} missing — run `python3 -m auto_parts_search.search_hybrid build-cache`")
    # Verify Meilisearch is reachable
    try:
        r = requests.get(f"{MEILI_URL}/health", timeout=3)
        if r.status_code == 200:
            print(f"[api] meilisearch reachable at {MEILI_URL}")
        else:
            print(f"[api] WARNING: meilisearch returned {r.status_code}")
    except Exception as e:
        print(f"[api] WARNING: meilisearch unreachable ({e})")
    yield


# ---------- schemas ----------

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=400, description="User query in any script")
    k: int = Field(10, ge=1, le=50, description="Number of results")


class SearchHit(BaseModel):
    rank: int
    part_id: str
    name: str
    fused_score: float
    bm25_rank: int | None
    embedding_rank: int | None


class SearchResponse(BaseModel):
    query: str
    query_class: Literal[
        "part_number", "hindi_hinglish", "symptom", "brand_as_generic", "exact_english"
    ]
    weights: dict
    classification_reason: str
    hits: list[SearchHit]
    latency_ms: float


class ClassifyResponse(BaseModel):
    query: str
    query_class: str
    bm25_weight: float
    embedding_weight: float
    evidence: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    meilisearch: bool
    v3_cache: bool
    bridges: bool


# ---------- app ----------

app = FastAPI(
    title="auto-parts-search",
    version="1.0.0",
    description="Hindi/Hinglish auto-parts search — hybrid BM25 + fine-tuned BGE-m3 embeddings",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------- endpoints ----------

@app.get("/", tags=["meta"])
def root():
    return {
        "service": "auto-parts-search",
        "version": "1.0.0",
        "endpoints": ["/search (GET/POST)", "/classify", "/health", "/stats"],
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health():
    meili_ok = False
    try:
        r = requests.get(f"{MEILI_URL}/health", timeout=2)
        meili_ok = r.status_code == 200
    except Exception:
        pass
    v3_ok = EMB_PATH.exists() and IDS_PATH.exists()
    bridges_ok = True
    try:
        s = bridge_stats()
        bridges_ok = s["roman_to_devanagari_entries"] > 0
    except Exception:
        bridges_ok = False

    all_ok = meili_ok and v3_ok and bridges_ok
    status = "ok" if all_ok else ("degraded" if (meili_ok or v3_ok) else "down")
    return HealthResponse(status=status, meilisearch=meili_ok, v3_cache=v3_ok, bridges=bridges_ok)


@app.get("/classify", response_model=ClassifyResponse, tags=["debug"])
def classify_endpoint(q: str = Query(..., min_length=1, max_length=400)):
    c = classify(q)
    return ClassifyResponse(
        query=q,
        query_class=c.query_class,
        bm25_weight=c.bm25_weight,
        embedding_weight=c.embedding_weight,
        evidence=c.evidence,
    )


def _run_search(query: str, k: int) -> SearchResponse:
    if not EMB_PATH.exists():
        raise HTTPException(status_code=503, detail="v3 corpus cache missing — run build-cache")
    t0 = time.perf_counter()
    cls = classify(query)
    try:
        hits = hybrid_search(query, k=k, k_candidates=max(k * 3, 30))
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")
    dt = (time.perf_counter() - t0) * 1000
    return SearchResponse(
        query=query,
        query_class=cls.query_class,
        weights={"bm25": cls.bm25_weight, "embedding": cls.embedding_weight},
        classification_reason=cls.evidence,
        hits=[
            SearchHit(
                rank=i + 1,
                part_id=h.part_id,
                name=h.name,
                fused_score=round(h.fused_score, 6),
                bm25_rank=h.bm25_rank,
                embedding_rank=h.emb_rank,
            )
            for i, h in enumerate(hits)
        ],
        latency_ms=round(dt, 2),
    )


@app.post("/search", response_model=SearchResponse, tags=["search"])
def search_post(req: SearchRequest):
    return _run_search(req.query, req.k)


@app.get("/search", response_model=SearchResponse, tags=["search"])
def search_get(
    q: str = Query(..., min_length=1, max_length=400),
    k: int = Query(10, ge=1, le=50),
):
    return _run_search(q, k)


# ---------- demo multi-tenant endpoints ----------

class CatalogUploadProduct(BaseModel):
    id: str | None = Field(None, description="Optional SKU ID; auto-generated if missing")
    name: str = Field(..., min_length=2, max_length=500)
    brand: str | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    description: str | None = None


class CatalogUploadRequest(BaseModel):
    name: str | None = Field(None, max_length=100, description="Friendly session label (e.g. 'Pikpart test')")
    products: list[CatalogUploadProduct] = Field(..., min_length=1, max_length=10000)


@app.post("/demo/catalog", tags=["demo"], summary="Upload a catalog and get a private demo session")
def demo_upload(req: CatalogUploadRequest):
    """Upload up to 10,000 products. Returns a session_id + per-session search URL.

    Session is isolated (your data only), auto-expires in 24 hours, and is
    kept in memory — restart wipes sessions. Purely a demo layer.
    """
    try:
        result = demo_tenant.upload_catalog(
            name=req.name,
            products=[p.model_dump(exclude_none=True) for p in req.products],
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"upload failed: {e}")


@app.get("/demo/{sid}", tags=["demo"], summary="Session metadata + sample products")
def demo_status(sid: str):
    s = demo_tenant.session_summary(sid)
    if not s:
        raise HTTPException(status_code=404, detail=f"session {sid} not found or expired")
    return s


@app.get("/demo/{sid}/search", tags=["demo"], summary="Search within an uploaded catalog")
def demo_search(
    sid: str,
    q: str = Query(..., min_length=1, max_length=400),
    k: int = Query(10, ge=1, le=50),
):
    try:
        t0 = time.perf_counter()
        result = demo_tenant.search_in_session(sid, q, k=k)
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {sid} not found or expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")


@app.delete("/demo/{sid}", tags=["demo"], summary="Explicitly delete a session")
def demo_delete(sid: str):
    ok = demo_tenant.delete_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail=f"session {sid} not found")
    return {"deleted": sid}


@app.get("/demo", tags=["demo"], summary="List active demo sessions")
def demo_list():
    return {"sessions": demo_tenant.list_sessions()}


@app.get("/stats", tags=["meta"])
def stats():
    out: dict = {"bridges": bridge_stats()}
    try:
        out["meilisearch"] = _meili("GET", f"/indexes/{INDEX_NAME}/stats")
    except Exception as e:
        out["meilisearch"] = {"error": str(e)}
    out["v3_cache"] = {
        "exists": EMB_PATH.exists(),
        "path": str(EMB_PATH),
    }
    if EMB_PATH.exists():
        import numpy as np
        emb = np.load(EMB_PATH, mmap_mode="r")
        out["v3_cache"]["shape"] = list(emb.shape)
    return out
