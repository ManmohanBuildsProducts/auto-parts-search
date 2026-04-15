"""T305 δ — grid-search hybrid RRF fusion weights per class on round-2 judged data.

Current weights (auto_parts_search/query_classifier.WEIGHTS) were tuned against
round 1 (2121 KG corpus). Round 2 (26K production corpus) has different signal
distribution — re-tune per class via coordinate descent.

Objective: maximize graded nDCG@10 on round-2 judged pool.

Approach:
    1. Precompute BM25 top-30 + v3 top-30 per query once (cached).
    2. For each classifier class, sweep its bm25_weight ∈ [0, 1] in 0.1 steps
       while holding other classes at current best. Keep best.
    3. Repeat (coordinate descent) for 2 passes — typically converges.
    4. Report tuned weights + delta vs current.

Output: `data/training/experiments/2026-04-15-bench-production/hybrid_tuned.json`
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import numpy as np

from auto_parts_search.query_classifier import classify, WEIGHTS
from auto_parts_search.search_bm25 import search as bm25_search
from auto_parts_search.tokenizer import IndicTokenizer

from scripts import _embed_api
_embed_api.CACHE_DIR = Path("data/external/processed/bench_round2")
from scripts._embed_api import embed  # noqa: E402

ROUND_DIR = Path("data/training/experiments/2026-04-15-bench-production")
CORPUS_PATH = ROUND_DIR / "round2_corpus.json"
GRADED_PATH = ROUND_DIR / "round2_graded.jsonl"
BENCHMARK_PATH = Path("data/training/golden/benchmark_dev.json")
OUT_PATH = ROUND_DIR / "hybrid_tuned.json"

K_RRF = 60
K_CAND = 30


def dcg(rels): return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def main() -> None:
    corpus = json.loads(CORPUS_PATH.read_text())
    ids = corpus["ids"]
    texts = corpus["texts"]
    id_to_idx = {pid: i for i, pid in enumerate(ids)}

    bench = json.loads(BENCHMARK_PATH.read_text())
    queries = [b["query"] for b in bench]

    graded = [json.loads(l) for l in GRADED_PATH.read_text().splitlines() if l.strip()]
    q_to_grade = {g["query"]: g for g in graded}

    # Pre-compute once
    print("encoding v3 over 26K (cached)...")
    v3_d = embed("v3-ours", texts, role="doc")
    v3_q = embed("v3-ours", queries, role="query")
    v3_sims = v3_q @ v3_d.T

    tok = IndicTokenizer()
    print("running BM25 for 149 queries (Meilisearch)...")
    raw = []  # per query: {bm25_ranks, emb_ranks, class, grade_map, ideal_idcg}
    for qi, b in enumerate(bench):
        q = b["query"]
        cls = classify(q)
        bm25_hits = bm25_search(q, k=K_CAND, tokenizer=tok)
        bm25_ranks = {}
        for r, h in enumerate(bm25_hits, 1):
            if h.part_id in id_to_idx:
                bm25_ranks[h.part_id] = r
        emb_order = np.argsort(-v3_sims[qi])[:K_CAND]
        emb_ranks = {ids[int(i)]: r + 1 for r, i in enumerate(emb_order)}

        if q not in q_to_grade:
            raw.append(None)
            continue
        g = q_to_grade[q]
        id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))
        ideal = sorted(g["grades"], reverse=True)[:10]
        idcg = dcg(ideal) or 1.0
        raw.append({
            "query": q,
            "class": cls.query_class,
            "bm25_ranks": bm25_ranks,
            "emb_ranks": emb_ranks,
            "id_to_grade": id_to_grade,
            "idcg": idcg,
        })
        if (qi + 1) % 30 == 0:
            print(f"  bm25 {qi+1}/{len(bench)}")

    def ndcg_at_10(weights: dict) -> tuple[float, dict]:
        """Compute mean nDCG@10 given per-class (bm25_w, emb_w)."""
        ndcgs = []
        by_class: dict[str, list[float]] = defaultdict(list)
        for item in raw:
            if item is None:
                continue
            bw, ew = weights[item["class"]]
            all_ids = set(item["bm25_ranks"]) | set(item["emb_ranks"])
            scores = {}
            for pid in all_ids:
                s = 0.0
                if pid in item["bm25_ranks"]:
                    s += bw / (K_RRF + item["bm25_ranks"][pid])
                if pid in item["emb_ranks"]:
                    s += ew / (K_RRF + item["emb_ranks"][pid])
                scores[pid] = s
            top = sorted(scores.items(), key=lambda x: -x[1])[:10]
            grades = [item["id_to_grade"].get(pid, 0) for pid, _ in top]
            ndcg = dcg(grades) / item["idcg"]
            ndcgs.append(ndcg)
            by_class[item["class"]].append(ndcg)
        return float(np.mean(ndcgs)), {c: float(np.mean(v)) for c, v in by_class.items()}

    current = deepcopy(WEIGHTS)  # dict: class -> (bm25_w, emb_w)
    classes = list(current.keys())

    # Baseline
    base_ndcg, base_by = ndcg_at_10(current)
    print(f"\nBaseline (current WEIGHTS): overall nDCG@10 = {base_ndcg:.4f}")
    for c in classes:
        print(f"   {c:20s} bm25={current[c][0]:.2f}  nDCG@10={base_by.get(c, 0):.3f}")

    # Coordinate descent: sweep each class's bm25 weight; emb_w = 1 - bm25_w
    grid = [round(0.1 * i, 1) for i in range(0, 11)]
    best = deepcopy(current)
    best_ndcg = base_ndcg

    for pass_i in range(2):
        changed = False
        print(f"\n--- pass {pass_i+1} ---")
        for c in classes:
            per_w = {}
            for bw in grid:
                trial = deepcopy(best)
                trial[c] = (bw, round(1.0 - bw, 2))
                overall, by = ndcg_at_10(trial)
                per_w[bw] = (overall, by.get(c, 0))
            best_w = max(per_w, key=lambda w: per_w[w][0])
            best_cls_w, best_cls_nd = per_w[best_w][0], per_w[best_w][1]
            if best_cls_w > best_ndcg + 1e-6:
                print(f"  {c:20s}  bm25 {best[c][0]:.1f} -> {best_w:.1f}   overall {best_ndcg:.4f} -> {best_cls_w:.4f}   class nDCG {per_w[best[c][0]][1]:.3f} -> {best_cls_nd:.3f}")
                best[c] = (best_w, round(1.0 - best_w, 2))
                best_ndcg = best_cls_w
                changed = True
            else:
                print(f"  {c:20s}  stays bm25={best[c][0]:.1f} (best trial {best_w:.1f} gives {best_cls_w:.4f} <= {best_ndcg:.4f})")
        if not changed:
            print("  (no improvements this pass; converged)")
            break

    tuned_ndcg, tuned_by = ndcg_at_10(best)
    print(f"\n=== TUNED ===")
    print(f"overall nDCG@10: {base_ndcg:.4f} -> {tuned_ndcg:.4f}   Δ = {tuned_ndcg - base_ndcg:+.4f}")
    for c in classes:
        old_w = current[c][0]
        new_w = best[c][0]
        delta = tuned_by.get(c, 0) - base_by.get(c, 0)
        print(f"  {c:20s}  bm25 {old_w:.1f} -> {new_w:.1f}   class nDCG {base_by.get(c,0):.3f} -> {tuned_by.get(c,0):.3f}  Δ={delta:+.3f}")

    OUT_PATH.write_text(json.dumps({
        "baseline_weights": current,
        "tuned_weights": {c: list(v) for c, v in best.items()},
        "baseline_ndcg@10": base_ndcg,
        "tuned_ndcg@10": tuned_ndcg,
        "baseline_by_class": base_by,
        "tuned_by_class": tuned_by,
    }, indent=2))
    print(f"\nsaved -> {OUT_PATH}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
