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

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
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
    slug: str | None = Field(None, max_length=60, description="Optional named slug for the demo URL, e.g. 'pikpart'")
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
            slug=req.slug,
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


def _require_session_key(sid: str, key: str | None, x_api_key: str | None) -> None:
    provided = key or x_api_key
    ok, reason = demo_tenant.check_session_auth(sid, provided)
    if not ok:
        if reason == "session not found":
            raise HTTPException(status_code=404, detail=f"session {sid} not found or expired")
        raise HTTPException(status_code=401, detail=reason)


@app.get("/demo/{sid}/search", tags=["demo"], summary="Search within an uploaded catalog")
def demo_search(
    sid: str,
    q: str = Query(..., min_length=1, max_length=400),
    k: int = Query(10, ge=1, le=50),
    key: str | None = Query(None, description="Session API key; or pass X-API-Key header"),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    _require_session_key(sid, key, x_api_key)
    try:
        t0 = time.perf_counter()
        result = demo_tenant.search_in_session(sid, q, k=k)
        result["latency_ms"] = round((time.perf_counter() - t0) * 1000, 2)
        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"session {sid} not found or expired")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"search failed: {e}")


@app.get("/demo/{sid}/try", tags=["demo"], include_in_schema=False,
         summary="Prospect-facing search UI (static HTML)")
def demo_try_ui(
    sid: str,
    key: str | None = Query(None),
    x_api_key: str | None = Header(None, alias="X-API-Key"),
):
    _require_session_key(sid, key, x_api_key)
    html_path = Path(__file__).parent / "static" / "try.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="try.html missing")
    return FileResponse(html_path, media_type="text/html")


@app.delete("/demo/{sid}", tags=["demo"], summary="Explicitly delete a session")
def demo_delete(sid: str):
    ok = demo_tenant.delete_session(sid)
    if not ok:
        raise HTTPException(status_code=404, detail=f"session {sid} not found")
    return {"deleted": sid}


# ---------- async job flow for large catalogs ----------

class CatalogStartRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    slug: str | None = Field(None, max_length=60)


class CatalogBatchRequest(BaseModel):
    products: list[CatalogUploadProduct] = Field(..., min_length=1, max_length=10000)


class CatalogUrlIngestRequest(BaseModel):
    name: str | None = Field(None, max_length=100)
    slug: str | None = Field(None, max_length=60)
    source_url: str = Field(..., description="HTTP(S) URL returning JSONL (one product per line)")


@app.post("/demo/catalog/start", tags=["demo-async"],
          summary="Start a job for a large catalog (batched upload)")
def demo_catalog_start(req: CatalogStartRequest):
    """Returns a job_id. Send products via /demo/catalog/{jid}/batch (up to 10K per
    call, up to 500K total per job), then POST /commit to trigger embedding.
    """
    return demo_tenant.start_job(req.name, slug=req.slug)


@app.post("/demo/catalog/{jid}/batch", tags=["demo-async"],
          summary="Append a batch of products to a job (max 10K per call)")
def demo_catalog_batch(jid: str, req: CatalogBatchRequest):
    try:
        return demo_tenant.append_to_job(
            jid, [p.model_dump(exclude_none=True) for p in req.products]
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"job {jid} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/demo/catalog/{jid}/commit", tags=["demo-async"],
          summary="Kick off async embedding + indexing (returns 202 Accepted)")
def demo_catalog_commit(jid: str):
    try:
        return demo_tenant.commit_job(jid)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"job {jid} not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/demo/catalog/ingest-url", tags=["demo-async"],
          summary="Ingest a JSONL catalog from a URL (server fetches + embeds)")
def demo_catalog_url(req: CatalogUrlIngestRequest):
    try:
        return demo_tenant.ingest_from_url(req.name, req.source_url, slug=req.slug)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/demo/catalog/{jid}", tags=["demo-async"], summary="Job progress + status")
def demo_catalog_status(jid: str):
    s = demo_tenant.job_status(jid)
    if not s:
        raise HTTPException(status_code=404, detail=f"job {jid} not found or expired")
    return s


@app.get("/demo/catalog", tags=["demo-async"], summary="List active jobs")
def demo_catalog_list():
    return {"jobs": demo_tenant.list_jobs()}


@app.delete("/demo/catalog/{jid}", tags=["demo-async"], summary="Cancel a job + drop its session")
def demo_catalog_delete(jid: str):
    if not demo_tenant.delete_job(jid):
        raise HTTPException(status_code=404, detail=f"job {jid} not found")
    return {"deleted": jid}


@app.get("/demo", tags=["demo"], summary="List active demo sessions")
def demo_list():
    return {"sessions": demo_tenant.list_sessions()}


# ---------- public catalog dashboard (scraped index) ----------

class CatalogSearchResponse(BaseModel):
    query: str
    query_class: str
    weights: dict
    classification_reason: str
    total_estimated: int
    hits: list[dict]
    facets: dict
    latency_ms: float
    timing: dict


@app.get("/catalog/try", tags=["catalog"], include_in_schema=False,
         summary="Public search dashboard over our scraped catalog index")
def catalog_try_ui():
    html_path = Path(__file__).parent / "static" / "catalog.html"
    if not html_path.exists():
        raise HTTPException(status_code=500, detail="catalog.html missing")
    return FileResponse(html_path, media_type="text/html")


@app.get("/catalog/search", response_model=CatalogSearchResponse, tags=["catalog"],
         summary="Faceted search over the scraped catalog index")
def catalog_search(
    q: str = Query(..., min_length=1, max_length=400),
    k: int = Query(20, ge=1, le=100),
    brand: str | None = Query(None),
    vehicle_make: str | None = Query(None),
    source: str | None = Query(None),
    doc_type: str | None = Query(None),
):
    """Like /search but returns facet counts (brand / vehicle_make / source /
    doc_type) for the sidebar filters, plus timing breakdown."""
    if not EMB_PATH.exists():
        raise HTTPException(status_code=503, detail="v3 corpus cache missing")

    t_all = time.perf_counter()

    # Classify + tokenize
    t0 = time.perf_counter()
    cls = classify(q)
    t_classify = (time.perf_counter() - t0) * 1000

    # Embedding query
    t0 = time.perf_counter()
    from auto_parts_search.search_hybrid import _encode_query, _load_corpus_cache, rrf_fuse
    import numpy as np
    q_emb = _encode_query(q)
    emb_corpus, corpus_ids, corpus_docs = _load_corpus_cache()
    scores = emb_corpus @ q_emb
    top_n = min(k * 3, 60)
    top_idx = np.argsort(-scores)[:top_n]
    emb_ranks = {corpus_ids[i]: rank + 1 for rank, i in enumerate(top_idx)}
    t_embed = (time.perf_counter() - t0) * 1000

    # BM25 + facets via Meilisearch
    t0 = time.perf_counter()
    from auto_parts_search.tokenizer import IndicTokenizer
    tok = IndicTokenizer()
    expanded = tok.query_tokens(q)
    q_str = " ".join(expanded)
    filters = []
    if brand:
        filters.append(f'brand = "{brand}"')
    if vehicle_make:
        filters.append(f'vehicle_make = "{vehicle_make}"')
    if source:
        filters.append(f'source = "{source}"')
    if doc_type:
        filters.append(f'doc_type = "{doc_type}"')
    body = {
        "q": q_str,
        "limit": k * 3,
        "matchingStrategy": "frequency",
        "showRankingScore": True,
        "facets": ["brand", "vehicle_make", "source", "doc_type"],
    }
    if filters:
        body["filter"] = " AND ".join(filters)
    bm = _meili("POST", f"/indexes/{INDEX_NAME}/search", body)
    t_bm25 = (time.perf_counter() - t0) * 1000

    # Fuse
    t0 = time.perf_counter()
    bm25_ranks = {h.get("part_id", h["id"]): i + 1 for i, h in enumerate(bm.get("hits", []))}
    id_to_bm = {h.get("part_id", h["id"]): h for h in bm.get("hits", [])}
    fused = rrf_fuse(bm25_ranks, emb_ranks, cls.bm25_weight, cls.embedding_weight)[:k]
    t_fuse = (time.perf_counter() - t0) * 1000

    # Hydrate results
    id_to_doc = {pid: doc for pid, doc in zip(corpus_ids, corpus_docs)}
    hits_out = []
    for rank, (pid, score) in enumerate(fused, start=1):
        bm_hit = id_to_bm.get(pid, {})
        name = bm_hit.get("name") or id_to_doc.get(pid, pid).split(" | ")[0]
        hits_out.append({
            "rank": rank,
            "part_id": pid,
            "name": name,
            "brand": bm_hit.get("brand", ""),
            "vehicle_make": bm_hit.get("vehicle_make", ""),
            "vehicle_model": bm_hit.get("vehicle_model", ""),
            "part_numbers": bm_hit.get("part_numbers", []),
            "source": bm_hit.get("source", ""),
            "doc_type": bm_hit.get("doc_type", ""),
            "fused_score": round(float(score), 6),
            "bm25_rank": bm25_ranks.get(pid),
            "embedding_rank": emb_ranks.get(pid),
        })

    dt_all = (time.perf_counter() - t_all) * 1000
    return CatalogSearchResponse(
        query=q,
        query_class=cls.query_class,
        weights={"bm25": cls.bm25_weight, "embedding": cls.embedding_weight},
        classification_reason=cls.evidence,
        total_estimated=bm.get("estimatedTotalHits", 0),
        hits=hits_out,
        facets=bm.get("facetDistribution", {}),
        latency_ms=round(dt_all, 2),
        timing={
            "classify_ms": round(t_classify, 2),
            "embed_ms": round(t_embed, 2),
            "bm25_ms": round(t_bm25, 2),
            "fuse_ms": round(t_fuse, 2),
        },
    )


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
