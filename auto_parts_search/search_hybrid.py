"""Hybrid BM25 + v3-embedding retrieval with Reciprocal Rank Fusion.

Pipeline:
  1. Classify query -> (bm25_weight, embedding_weight)
  2. BM25 top-K   via auto_parts_search.search_bm25
  3. Embedding top-K via cached v3 corpus embeddings + cosine
  4. RRF fusion with class-specific weights -> final top-k

Corpus embeddings are precomputed once and cached to disk
(data/external/processed/v3_corpus_embeddings.npy + part_ids.json).
Regenerate via `python3 -m auto_parts_search.search_hybrid build-cache`.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from auto_parts_search.query_classifier import classify
from auto_parts_search.search_bm25 import search as bm25_search
from auto_parts_search.tokenizer import IndicTokenizer

GRAPH_DB = Path("data/knowledge_graph/graph.db")
CACHE_DIR = Path("data/external/processed")
EMB_PATH = CACHE_DIR / "v3_corpus_embeddings.npy"
IDS_PATH = CACHE_DIR / "v3_corpus_part_ids.json"
DOCS_PATH = CACHE_DIR / "v3_corpus_docs.json"
MODEL_NAME = "ManmohanBuildsProducts/auto-parts-search-v3"


# ---------- corpus cache ----------

def load_corpus_strings() -> tuple[list[str], list[str]]:
    """Mirror training.evaluate.load_corpus structure (name + aliases + system)."""
    conn = sqlite3.connect(GRAPH_DB)
    parts = list(conn.execute("SELECT id, name FROM nodes WHERE type='part'"))
    aliases: dict[str, list[str]] = defaultdict(list)
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias'"
    ):
        aliases[part_id].append(alias_name)
    systems: dict[str, list[str]] = defaultdict(list)
    for part_id, sys_name in conn.execute(
        "SELECT e.src, n.name FROM edges e JOIN nodes n ON n.id = e.dst "
        "WHERE e.type='in_system' AND n.type='system'"
    ):
        systems[part_id].append(sys_name)
    conn.close()

    ids: list[str] = []
    docs: list[str] = []
    for pid, name in parts:
        al = aliases.get(pid, [])
        sy = systems.get(pid, [])
        doc = name
        if al:
            doc += " | " + ", ".join(al)
        if sy:
            doc += " | system: " + ", ".join(sy)
        ids.append(pid)
        docs.append(doc)
    return ids, docs


def build_cache(model_name: str = MODEL_NAME) -> None:
    from sentence_transformers import SentenceTransformer
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ids, docs = load_corpus_strings()
    print(f"encoding {len(docs)} docs with {model_name}...")
    model = SentenceTransformer(model_name, trust_remote_code=True)
    emb = model.encode(docs, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    np.save(EMB_PATH, emb.astype(np.float32))
    IDS_PATH.write_text(json.dumps(ids, ensure_ascii=False))
    DOCS_PATH.write_text(json.dumps(docs, ensure_ascii=False))
    print(f"saved {emb.shape} -> {EMB_PATH}")


_model_cache = {}


def _encode_query(query: str, model_name: str = MODEL_NAME) -> np.ndarray:
    if model_name not in _model_cache:
        from sentence_transformers import SentenceTransformer
        _model_cache[model_name] = SentenceTransformer(model_name, trust_remote_code=True)
    m = _model_cache[model_name]
    return m.encode([query], convert_to_numpy=True, normalize_embeddings=True)[0]


_corpus_cache: dict = {}


def _load_corpus_cache() -> tuple[np.ndarray, list[str], list[str]]:
    if "emb" not in _corpus_cache:
        if not EMB_PATH.exists():
            raise FileNotFoundError(f"Run build-cache first: {EMB_PATH} missing")
        _corpus_cache["emb"] = np.load(EMB_PATH)
        _corpus_cache["ids"] = json.loads(IDS_PATH.read_text())
        _corpus_cache["docs"] = json.loads(DOCS_PATH.read_text())
    return _corpus_cache["emb"], _corpus_cache["ids"], _corpus_cache["docs"]


# ---------- hybrid search ----------

@dataclass
class HybridHit:
    part_id: str
    name: str
    fused_score: float
    bm25_rank: int | None
    emb_rank: int | None
    classification: str


def embedding_topk(query: str, k: int = 30) -> list[tuple[str, str, float]]:
    """Returns list of (part_id, doc_text, cosine_score) sorted by cosine desc."""
    emb, ids, docs = _load_corpus_cache()
    q = _encode_query(query)
    scores = emb @ q  # cosine since normalized
    top_idx = np.argsort(-scores)[:k]
    return [(ids[i], docs[i], float(scores[i])) for i in top_idx]


def rrf_fuse(
    bm25_ranks: dict[str, int],
    emb_ranks: dict[str, int],
    w_bm25: float,
    w_emb: float,
    k_rrf: int = 60,
) -> list[tuple[str, float]]:
    """Reciprocal Rank Fusion. Returns [(part_id, score)] sorted desc."""
    all_ids = set(bm25_ranks) | set(emb_ranks)
    scores: dict[str, float] = {}
    for pid in all_ids:
        s = 0.0
        if pid in bm25_ranks:
            s += w_bm25 * (1.0 / (k_rrf + bm25_ranks[pid]))
        if pid in emb_ranks:
            s += w_emb * (1.0 / (k_rrf + emb_ranks[pid]))
        scores[pid] = s
    return sorted(scores.items(), key=lambda x: -x[1])


def search(
    query: str,
    k: int = 20,
    k_candidates: int = 30,
    tokenizer: IndicTokenizer | None = None,
) -> list[HybridHit]:
    cls = classify(query)
    tok = tokenizer or IndicTokenizer()

    bm25_hits = bm25_search(query, k=k_candidates, tokenizer=tok)
    bm25_ranks = {h.part_id: i + 1 for i, h in enumerate(bm25_hits)}

    emb_hits = embedding_topk(query, k=k_candidates)
    emb_ranks = {pid: i + 1 for i, (pid, _, _) in enumerate(emb_hits)}

    fused = rrf_fuse(bm25_ranks, emb_ranks, cls.bm25_weight, cls.embedding_weight)[:k]

    # Attach names/info
    id_to_name: dict[str, str] = {}
    for h in bm25_hits:
        id_to_name[h.part_id] = h.name
    _, ids, docs = _load_corpus_cache()
    for pid, doc in zip(ids, docs):
        id_to_name.setdefault(pid, doc.split(" | ")[0])

    return [
        HybridHit(
            part_id=pid,
            name=id_to_name.get(pid, pid),
            fused_score=score,
            bm25_rank=bm25_ranks.get(pid),
            emb_rank=emb_ranks.get(pid),
            classification=cls.query_class,
        )
        for pid, score in fused
    ]


# ---------- CLI ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build-cache", "search", "classify"])
    ap.add_argument("query", nargs="?", default=None)
    ap.add_argument("--k", type=int, default=10)
    args = ap.parse_args()

    if args.cmd == "build-cache":
        build_cache()
        return

    if args.cmd == "classify":
        c = classify(args.query or "")
        print(f"class: {c.query_class}   weights: bm25={c.bm25_weight} emb={c.embedding_weight}   ({c.evidence})")
        return

    if args.cmd == "search":
        if not args.query:
            print("usage: search '<query>'")
            return
        hits = search(args.query, k=args.k)
        cls = hits[0].classification if hits else "?"
        print(f"classification: {cls}")
        for i, h in enumerate(hits, 1):
            b = f"bm{h.bm25_rank}" if h.bm25_rank is not None else "-"
            e = f"e{h.emb_rank}" if h.emb_rank is not None else "-"
            print(f"{i:2d}  [{h.fused_score:.4f}]  [{b:>4s}/{e:>4s}]  {h.name}")


if __name__ == "__main__":
    main()
