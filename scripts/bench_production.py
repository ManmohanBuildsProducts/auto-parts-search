"""T305 round 2 — production-scale benchmark over 26K corpus.

Answers: does production hybrid (v3+BM25) beat OpenAI text-embedding-3-large
over the FULL corpus the product actually searches (884 KG + 25,951 catalog)?

Round 1 restricted to 2,121 KG docs where BM25 had no part-number docs to
exact-match against. Round 2 uses the full 26,835-doc Meilisearch index.

Phases (split for checkpointing):
    python3.11 -m scripts.bench_production corpus   # pull 26K from Meili
    python3.11 -m scripts.bench_production embed    # embed 6 models (cached)
    python3.11 -m scripts.bench_production pool     # joint pool + sanity
    python3.11 -m scripts.bench_production judge    # DeepSeek V3 grades
    python3.11 -m scripts.bench_production hybrid   # production v3+BM25 ranking
    python3.11 -m scripts.bench_production score    # metrics vs judged pool
    python3.11 -m scripts.bench_production report   # markdown table
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import requests

ROUND = "round2"
OUT_DIR = Path("data/training/experiments/2026-04-15-bench-production")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORPUS_PATH = OUT_DIR / f"{ROUND}_corpus.json"
POOL_PATH = OUT_DIR / f"{ROUND}_joint_pool.json"
GRADED_PATH = OUT_DIR / f"{ROUND}_graded.jsonl"
HYBRID_RANKS_PATH = OUT_DIR / f"{ROUND}_hybrid_rankings.json"
HYBRID_TUNED_RANKS_PATH = OUT_DIR / f"{ROUND}_hybrid_rankings_tuned.json"
TUNED_WEIGHTS_PATH = OUT_DIR / "hybrid_tuned.json"
SCORES_PATH = OUT_DIR / f"{ROUND}_scores.json"
REPORT_PATH = Path("docs/eval_round2.md")

BENCHMARK_PATH = Path("data/training/golden/benchmark_dev.json")

MEILI_URL = "http://127.0.0.1:7700"
MEILI_KEY = "aps_local_dev_key_do_not_use_in_prod"

TOPK_POOL = 20
SANITY_QUERIES = ["brake pad", "spark plug", "6U7853952"]  # last = real part number in catalog
# Round-2 bench models — drop jina-v3 (API too slow for 26K embed). Round 1 already has it.
BENCH_MODELS_SKIP = {"jina-v3"}

# Use a separate cache dir so round1 2121-doc cache doesn't collide.
os.environ.setdefault("APS_BENCH_CACHE", "data/external/processed/bench_round2")


def _doc_text(d: dict) -> str:
    """Build searchable text for a doc (KG or catalog)."""
    parts = [d.get("name", "")]
    if d.get("aliases"):
        parts.append("aliases: " + ", ".join(d["aliases"]))
    if d.get("system"):
        parts.append("system: " + d["system"])
    if d.get("brand"):
        parts.append("brand: " + d["brand"])
    if d.get("vehicle_make"):
        parts.append("vehicle: " + d["vehicle_make"] + " " + (d.get("vehicle_model") or ""))
    if d.get("part_numbers"):
        parts.append("pn: " + " ".join(d["part_numbers"]))
    return " | ".join(p for p in parts if p and p != "vehicle:  ")


# --- Phase 0: pull corpus ---

def phase_corpus() -> dict:
    print("pulling 26K corpus from Meilisearch...")
    hdr = {"Authorization": f"Bearer {MEILI_KEY}"}
    docs: list[dict] = []
    offset = 0
    page = 1000
    while True:
        r = requests.get(
            f"{MEILI_URL}/indexes/parts/documents",
            params={
                "limit": page,
                "offset": offset,
                "fields": "id,part_id,name,aliases,system,doc_type,brand,vehicle_make,vehicle_model,part_numbers",
            },
            headers=hdr, timeout=60,
        )
        r.raise_for_status()
        batch = r.json()["results"]
        docs.extend(batch)
        if len(batch) < page:
            break
        offset += page
        print(f"  pulled {len(docs)}")
    print(f"  total: {len(docs)}")

    ids = [d["part_id"] for d in docs]
    texts = [_doc_text(d) for d in docs]

    data = {"ids": ids, "texts": texts, "meta": [{k: d.get(k) for k in ("doc_type", "brand", "vehicle_make")} for d in docs]}
    CORPUS_PATH.write_text(json.dumps(data, ensure_ascii=False))
    print(f"saved -> {CORPUS_PATH}")
    return data


def load_corpus() -> tuple[list[str], list[str], list[dict]]:
    if not CORPUS_PATH.exists():
        phase_corpus()
    d = json.loads(CORPUS_PATH.read_text())
    return d["ids"], d["texts"], d["meta"]


def load_queries() -> list[dict]:
    return json.loads(BENCHMARK_PATH.read_text())


# --- Phase A: embed ---

def phase_embed() -> dict[str, dict]:
    """Embed 26K corpus + 149 queries for all 6 models. Cached to its own dir."""
    # Override cache dir for round2 via monkey-patch
    from scripts import _embed_api
    _embed_api.CACHE_DIR = Path("data/external/processed/bench_round2")
    _embed_api.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    ids, texts, _ = load_corpus()
    bench = load_queries()
    queries = [b["query"] for b in bench]
    print(f"corpus: {len(texts)} docs | queries: {len(queries)}\n")

    from scripts._embed_api import MODELS, embed
    out = {}
    for mk in MODELS:
        if mk in BENCH_MODELS_SKIP:
            continue
        print(f"--- {mk} ---")
        t0 = time.time()
        d_emb = embed(mk, texts, role="doc")
        q_emb = embed(mk, queries, role="query")
        out[mk] = {"d_emb": d_emb, "q_emb": q_emb, "elapsed": time.time() - t0}
        print(f"  -> d={d_emb.shape} q={q_emb.shape} in {out[mk]['elapsed']:.1f}s\n")
    return out


# --- Phase B: pool ---

def phase_pool(embeds=None) -> dict:
    ids, texts, _ = load_corpus()
    bench = load_queries()
    if embeds is None:
        embeds = phase_embed()

    from scripts._embed_api import MODELS

    queries = [b["query"] for b in bench]
    per_model_topk = {}
    for mk, e in embeds.items():
        sims = e["q_emb"] @ e["d_emb"].T
        per_model_topk[mk] = np.argsort(-sims, axis=1)[:, :TOPK_POOL]

    joint_pool = []
    sizes = []
    for qi in range(len(queries)):
        seen = set()
        order = []
        for mk in MODELS:
            if mk not in embeds:
                continue
            for idx in per_model_topk[mk][qi]:
                i = int(idx)
                if i not in seen:
                    seen.add(i)
                    order.append(i)
        joint_pool.append(order)
        sizes.append(len(order))

    data = {
        "round": ROUND,
        "corpus_size": len(texts),
        "n_queries": len(queries),
        "topk_per_model": TOPK_POOL,
        "models": list(MODELS.keys()),
        "pool_sizes": sizes,
        "pool_stats": {
            "min": min(sizes), "max": max(sizes),
            "median": int(np.median(sizes)), "mean": float(np.mean(sizes)),
        },
        "per_query": [
            {
                "query": queries[qi],
                "query_type": bench[qi]["query_type"],
                "pool_idxs": joint_pool[qi],
                "pool_ids": [ids[i] for i in joint_pool[qi]],
                "pool_docs": [texts[i] for i in joint_pool[qi]],
            }
            for qi in range(len(queries))
        ],
    }
    POOL_PATH.write_text(json.dumps(data, ensure_ascii=False))
    print(f"\npool sizes: min={min(sizes)} median={int(np.median(sizes))} max={max(sizes)} mean={np.mean(sizes):.1f}")
    print(f"saved -> {POOL_PATH}")

    # Sanity
    print("\n=== SANITY (top-3 per model) ===")
    from scripts._embed_api import embed
    for sq in SANITY_QUERIES:
        print(f"\n  query: '{sq}'")
        for mk in MODELS:
            if mk not in embeds:
                continue
            e = embeds[mk]
            q = embed(mk, [sq], role="query", use_cache=True)[0]
            sims = e["d_emb"] @ q
            top3 = np.argsort(-sims)[:3]
            print(f"    {mk:18s}: {texts[top3[0]][:80]}")
            for i in top3[1:]:
                print(f"    {'':18s}  {texts[i][:80]}")
    return data


# --- Phase C: judge ---

def phase_judge() -> None:
    pool = json.loads(POOL_PATH.read_text())
    done = set()
    if GRADED_PATH.exists():
        for l in GRADED_PATH.read_text().splitlines():
            if l.strip():
                done.add(json.loads(l)["query"])
        print(f"resume: {len(done)}/{len(pool['per_query'])} already judged")

    from scripts.judge_benchmark import judge_with_deepseek
    api_key = os.environ["DEEPSEEK_API_KEY"]

    todo = [pq for pq in pool["per_query"] if pq["query"] not in done]
    print(f"to judge: {len(todo)}")
    t0 = time.time()
    with GRADED_PATH.open("a") as f:
        for qi, pq in enumerate(todo):
            print(f"[{qi+1}/{len(todo)}] ({pq['query_type']}) {pq['query'][:60]} (pool={len(pq['pool_docs'])})", flush=True)
            try:
                grades = judge_with_deepseek(pq["query"], pq["pool_docs"], api_key, model="deepseek-chat")
            except Exception as e:
                print(f"  SKIP: {e}", file=sys.stderr)
                continue
            rec = {
                "query": pq["query"],
                "query_type": pq["query_type"],
                "candidate_ids": pq["pool_ids"],
                "candidate_docs": pq["pool_docs"],
                "grades": grades,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            rel = sum(1 for g in grades if g == 2)
            mar = sum(1 for g in grades if g == 1)
            print(f"   -> rel={rel} mar={mar}")
    print(f"\ndone in {(time.time()-t0)/60:.1f} min -> {GRADED_PATH}")


# --- Phase D: hybrid ---

def _hybrid_rank(weights_override: dict | None = None) -> dict:
    """Core hybrid ranker. If weights_override given, use it instead of classifier defaults."""
    from auto_parts_search.query_classifier import classify
    from auto_parts_search.search_bm25 import search as bm25_search
    from auto_parts_search.tokenizer import IndicTokenizer

    ids, texts, _ = load_corpus()
    id_to_idx = {pid: i for i, pid in enumerate(ids)}
    bench = load_queries()

    # v3 dense over 26K (from round2 cache)
    from scripts import _embed_api
    _embed_api.CACHE_DIR = Path("data/external/processed/bench_round2")
    from scripts._embed_api import embed

    queries = [b["query"] for b in bench]
    v3_d = embed("v3-ours", texts, role="doc")
    v3_q = embed("v3-ours", queries, role="query")
    v3_sims = v3_q @ v3_d.T

    tok = IndicTokenizer()
    K_RRF = 60
    K_CAND = int(os.environ.get("HYBRID_K_CAND", "30"))
    TOP = int(os.environ.get("HYBRID_TOP", "20"))

    rankings = []
    classes = []
    for qi, q in enumerate(bench):
        cls = classify(q["query"])
        classes.append(cls.query_class)

        if weights_override and cls.query_class in weights_override:
            bw, ew = weights_override[cls.query_class]
        else:
            bw, ew = cls.bm25_weight, cls.embedding_weight

        bm25_hits = bm25_search(q["query"], k=K_CAND, tokenizer=tok)
        bm25_ranks = {}
        for r, h in enumerate(bm25_hits, 1):
            if h.part_id in id_to_idx:
                bm25_ranks[h.part_id] = r

        emb_order = np.argsort(-v3_sims[qi])[:K_CAND]
        emb_ranks = {ids[int(i)]: r + 1 for r, i in enumerate(emb_order)}

        all_ids = set(bm25_ranks) | set(emb_ranks)
        scores = {}
        for pid in all_ids:
            s = 0.0
            if pid in bm25_ranks:
                s += bw / (K_RRF + bm25_ranks[pid])
            if pid in emb_ranks:
                s += ew / (K_RRF + emb_ranks[pid])
            scores[pid] = s
        fused = sorted(scores.items(), key=lambda x: -x[1])[:TOP]
        rankings.append([pid for pid, _ in fused])

        if (qi + 1) % 30 == 0:
            print(f"  hybrid {qi+1}/{len(bench)}", flush=True)

    return {"queries": queries, "rankings": rankings, "classes": classes}


def phase_hybrid() -> dict:
    """Production hybrid (classifier default weights) + tuned hybrid if tuned weights exist."""
    out = _hybrid_rank(weights_override=None)
    HYBRID_RANKS_PATH.write_text(json.dumps(out, ensure_ascii=False))
    print(f"saved -> {HYBRID_RANKS_PATH}")
    if TUNED_WEIGHTS_PATH.exists():
        tuned = json.loads(TUNED_WEIGHTS_PATH.read_text())
        override = {c: tuple(v) for c, v in tuned["tuned_weights"].items()}
        print(f"computing tuned-weight hybrid with weights = {override}")
        out2 = _hybrid_rank(weights_override=override)
        HYBRID_TUNED_RANKS_PATH.write_text(json.dumps(out2, ensure_ascii=False))
        print(f"saved -> {HYBRID_TUNED_RANKS_PATH}")
    return out


# --- Phase E: score ---

def dcg(rels): return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ap_at_k(rels_bin, k):
    hits = 0; s = 0.0
    for i, r in enumerate(rels_bin[:k]):
        if r:
            hits += 1
            s += hits / (i + 1)
    tot = sum(1 for r in rels_bin if r)
    return (s / min(tot, k)) if tot else 0.0


def _score_ranking_seq(grade_seq: list[int], total_rel2: int) -> dict:
    gains_10 = grade_seq[:10]
    ideal_idcg_grades = sorted(grade_seq + [0] * 0, reverse=True)[:10]  # fallback: use observed grades
    idcg = dcg(sorted(grade_seq, reverse=True)[:10]) or 1.0
    # Actually ideal should come from full judged pool — caller will supply
    return {
        "gains_10": gains_10,
        "idcg_from_observed": idcg,
    }


def phase_score(embeds=None) -> dict:
    ids, texts, _ = load_corpus()
    id_to_idx = {pid: i for i, pid in enumerate(ids)}
    bench = load_queries()

    from scripts._embed_api import MODELS
    from scripts import _embed_api
    _embed_api.CACHE_DIR = Path("data/external/processed/bench_round2")

    if embeds is None:
        embeds = phase_embed()

    graded = [json.loads(l) for l in GRADED_PATH.read_text().splitlines() if l.strip()]
    q_to_grade = {g["query"]: g for g in graded}
    print(f"scoring against {len(graded)} judged queries")

    metrics_all = {}

    def score_rank_seq(grade_seq_top20, full_grades_in_pool):
        """Compute the 4 metrics given graded ranks at top-20 + full pool grades for ideal."""
        ideal = sorted(full_grades_in_pool, reverse=True)[:10]
        idcg = dcg(ideal) or 1.0
        ndcg = dcg(grade_seq_top20[:10]) / idcg
        total_rel2 = sum(1 for g in full_grades_in_pool if g == 2)
        if total_rel2:
            recall5 = sum(1 for x in grade_seq_top20[:5] if x == 2) / total_rel2
        else:
            recall5 = 0.0
        p1 = 1.0 if grade_seq_top20[0] >= 1 else 0.0
        rels_bin = [1 if g >= 1 else 0 for g in grade_seq_top20]
        map_v = ap_at_k(rels_bin, 10)
        zero = not any(g >= 1 for g in grade_seq_top20[:10])
        return ndcg, recall5, p1, map_v, zero

    # Embedding-only models
    for mk in MODELS:
        if mk not in embeds:
            continue
        q_emb = embeds[mk]["q_emb"]
        d_emb = embeds[mk]["d_emb"]
        sims = q_emb @ d_emb.T

        ndcgs = []; recalls5 = []; p1 = []; maps = []; z = 0
        ndcg_by_type = defaultdict(list)
        for qi, q in enumerate(bench):
            if q["query"] not in q_to_grade:
                continue
            g = q_to_grade[q["query"]]
            id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))
            full_order = np.argsort(-sims[qi])[:20]
            grade_seq = [id_to_grade.get(ids[int(i)], 0) for i in full_order]

            n, r5, pp, mp, zr = score_rank_seq(grade_seq, g["grades"])
            ndcgs.append(n); recalls5.append(r5); p1.append(pp); maps.append(mp)
            if zr: z += 1
            ndcg_by_type[q["query_type"]].append(n)

        metrics_all[mk] = {
            "ndcg@10_graded": float(np.mean(ndcgs)),
            "recall@5_graded": float(np.mean(recalls5)),
            "p@1": float(np.mean(p1)),
            "map@10": float(np.mean(maps)),
            "zero_result_rate@10": z / max(1, len(ndcgs)),
            "n_scored": len(ndcgs),
            "ndcg@10_by_type": {t: {"score": float(np.mean(v)), "n": len(v)} for t, v in sorted(ndcg_by_type.items())},
        }
        print(f"  {mk:18s}  nDCG@10={metrics_all[mk]['ndcg@10_graded']:.3f}  R@5={metrics_all[mk]['recall@5_graded']:.3f}  P@1={metrics_all[mk]['p@1']:.3f}  MAP@10={metrics_all[mk]['map@10']:.3f}")

    # Hybrid rows (baseline and tuned)
    def _score_hybrid(path: Path, label: str) -> None:
        if not path.exists():
            return
        h = json.loads(path.read_text())
        q_to_ranking = dict(zip(h["queries"], h["rankings"]))
        ndcgs = []; recalls5 = []; p1 = []; maps = []; z = 0
        ndcg_by_type = defaultdict(list)
        for q in bench:
            if q["query"] not in q_to_grade or q["query"] not in q_to_ranking:
                continue
            g = q_to_grade[q["query"]]
            id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))
            ranked_ids = q_to_ranking[q["query"]]
            grade_seq = [id_to_grade.get(pid, 0) for pid in ranked_ids[:20]]
            while len(grade_seq) < 20:
                grade_seq.append(0)
            n, r5, pp, mp, zr = score_rank_seq(grade_seq, g["grades"])
            ndcgs.append(n); recalls5.append(r5); p1.append(pp); maps.append(mp)
            if zr: z += 1
            ndcg_by_type[q["query_type"]].append(n)
        metrics_all[label] = {
            "ndcg@10_graded": float(np.mean(ndcgs)),
            "recall@5_graded": float(np.mean(recalls5)),
            "p@1": float(np.mean(p1)),
            "map@10": float(np.mean(maps)),
            "zero_result_rate@10": z / max(1, len(ndcgs)),
            "n_scored": len(ndcgs),
            "ndcg@10_by_type": {t: {"score": float(np.mean(v)), "n": len(v)} for t, v in sorted(ndcg_by_type.items())},
        }
        print(f"  {label:24s}  nDCG@10={metrics_all[label]['ndcg@10_graded']:.3f}  R@5={metrics_all[label]['recall@5_graded']:.3f}  P@1={metrics_all[label]['p@1']:.3f}  MAP@10={metrics_all[label]['map@10']:.3f}")

    _score_hybrid(HYBRID_RANKS_PATH, "v3+bm25-hybrid")
    _score_hybrid(HYBRID_TUNED_RANKS_PATH, "v3+bm25-hybrid-tuned")

    SCORES_PATH.write_text(json.dumps(metrics_all, indent=2))
    print(f"\nsaved -> {SCORES_PATH}")
    return metrics_all


# --- Phase F: report ---

def phase_report() -> None:
    scores = json.loads(SCORES_PATH.read_text())
    lines = []
    lines.append(f"# Eval — Round 2 (T305 production-scale benchmark)\n")
    lines.append(f"Corpus: 26,835 docs (884 KG + 25,951 catalog). Queries: 149 dev. Judge: DeepSeek V3.\n")
    lines.append("## Overall scoreboard\n")
    lines.append("| Model | nDCG@10 | Recall@5 | P@1 | MAP@10 | 0-result% |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for mk, m in scores.items():
        lines.append(f"| `{mk}` | {m['ndcg@10_graded']:.3f} | {m['recall@5_graded']:.3f} | {m['p@1']:.3f} | {m['map@10']:.3f} | {m['zero_result_rate@10']*100:.1f}% |")
    types = sorted({t for m in scores.values() for t in m["ndcg@10_by_type"]})
    lines.append("\n## Per-category nDCG@10\n")
    first_model_types = scores[list(scores)[0]]["ndcg@10_by_type"]
    header = "| Model | " + " | ".join(f"{t} (n={first_model_types[t]['n']})" for t in types) + " |"
    lines.append(header)
    lines.append("|---" * (len(types) + 1) + "|")
    for mk, m in scores.items():
        row = [f"`{mk}`"] + [f"{m['ndcg@10_by_type'].get(t, {'score':0})['score']:.3f}" for t in types]
        lines.append("| " + " | ".join(row) + " |")
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"report -> {REPORT_PATH}")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["corpus", "embed", "pool", "judge", "hybrid", "score", "report"])
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    {"corpus": phase_corpus, "embed": phase_embed, "pool": phase_pool,
     "judge": phase_judge, "hybrid": phase_hybrid, "score": phase_score,
     "report": phase_report}[args.phase]()


if __name__ == "__main__":
    main()
