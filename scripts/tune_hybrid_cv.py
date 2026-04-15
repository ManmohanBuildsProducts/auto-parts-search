"""T305 δ-validate — 3-fold cross-validation on hybrid fusion tuning.

Addresses the dev-set-overfitting concern in scripts/tune_hybrid.py:
that script tunes + scores on the same 149 queries.

CV protocol:
    1. Stratified 3-fold split by benchmark.query_type (26-27 hindi/exact/symptom,
       ~22 part_number/brand/misspelled -> balanced folds).
    2. For each fold k:
         - Tune fusion weights via coordinate descent on the OTHER 2 folds (~100 q).
         - Apply tuned weights to held-out fold (~50 q), record held-out nDCG@10.
    3. Average held-out nDCG across 3 folds -> generalization estimate.
    4. Compare to the all-data tuned nDCG (0.430) -> overfit gap.

Output: `data/training/experiments/2026-04-15-bench-production/hybrid_cv.json`
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from random import Random

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
OUT_PATH = ROUND_DIR / "hybrid_cv.json"

K_RRF = 60
K_CAND = 30
N_FOLDS = 3
SEED = 42


def dcg(rels): return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def precompute_raw() -> list[dict]:
    corpus = json.loads(CORPUS_PATH.read_text())
    ids = corpus["ids"]
    texts = corpus["texts"]
    id_to_idx = {pid: i for i, pid in enumerate(ids)}
    bench = json.loads(BENCHMARK_PATH.read_text())
    queries = [b["query"] for b in bench]

    graded = [json.loads(l) for l in GRADED_PATH.read_text().splitlines() if l.strip()]
    q_to_grade = {g["query"]: g for g in graded}

    print("encoding v3 over 26K (cached)...")
    v3_d = embed("v3-ours", texts, role="doc")
    v3_q = embed("v3-ours", queries, role="query")
    v3_sims = v3_q @ v3_d.T

    tok = IndicTokenizer()
    print("running BM25 for 149 queries...")
    raw = []
    for qi, b in enumerate(bench):
        q = b["query"]
        if q not in q_to_grade:
            raw.append(None)
            continue
        cls = classify(q)
        bm25_hits = bm25_search(q, k=K_CAND, tokenizer=tok)
        bm25_ranks = {}
        for r, h in enumerate(bm25_hits, 1):
            if h.part_id in id_to_idx:
                bm25_ranks[h.part_id] = r
        emb_order = np.argsort(-v3_sims[qi])[:K_CAND]
        emb_ranks = {ids[int(i)]: r + 1 for r, i in enumerate(emb_order)}
        g = q_to_grade[q]
        id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))
        idcg = dcg(sorted(g["grades"], reverse=True)[:10]) or 1.0
        raw.append({
            "query": q,
            "query_type": b["query_type"],
            "class": cls.query_class,
            "bm25_ranks": bm25_ranks,
            "emb_ranks": emb_ranks,
            "id_to_grade": id_to_grade,
            "idcg": idcg,
        })
        if (qi + 1) % 30 == 0:
            print(f"  bm25 {qi+1}/{len(bench)}")
    return [r for r in raw if r is not None]


def stratified_kfold(items: list[dict], k: int, seed: int) -> list[list[int]]:
    """Return k lists of indices into items, stratified by query_type."""
    by_type: dict[str, list[int]] = defaultdict(list)
    for i, it in enumerate(items):
        by_type[it["query_type"]].append(i)
    rng = Random(seed)
    folds: list[list[int]] = [[] for _ in range(k)]
    for t, idxs in by_type.items():
        rng.shuffle(idxs)
        for i, idx in enumerate(idxs):
            folds[i % k].append(idx)
    return folds


def ndcg_on_subset(items: list[dict], subset_idxs: list[int], weights: dict) -> tuple[float, dict]:
    ndcgs = []
    by_class: dict[str, list[float]] = defaultdict(list)
    for i in subset_idxs:
        it = items[i]
        bw, ew = weights[it["class"]]
        all_ids = set(it["bm25_ranks"]) | set(it["emb_ranks"])
        scores = {}
        for pid in all_ids:
            s = 0.0
            if pid in it["bm25_ranks"]:
                s += bw / (K_RRF + it["bm25_ranks"][pid])
            if pid in it["emb_ranks"]:
                s += ew / (K_RRF + it["emb_ranks"][pid])
            scores[pid] = s
        top = sorted(scores.items(), key=lambda x: -x[1])[:10]
        grades = [it["id_to_grade"].get(pid, 0) for pid, _ in top]
        ndcg = dcg(grades) / it["idcg"]
        ndcgs.append(ndcg)
        by_class[it["class"]].append(ndcg)
    return float(np.mean(ndcgs)) if ndcgs else 0.0, {c: float(np.mean(v)) for c, v in by_class.items()}


def coord_descent(items: list[dict], train_idxs: list[int], init: dict, passes: int = 2) -> tuple[dict, float]:
    current = deepcopy(init)
    best_score, _ = ndcg_on_subset(items, train_idxs, current)
    grid = [round(0.1 * i, 1) for i in range(0, 11)]
    for _ in range(passes):
        changed = False
        for c in list(current.keys()):
            for bw in grid:
                trial = deepcopy(current)
                trial[c] = (bw, round(1.0 - bw, 2))
                s, _ = ndcg_on_subset(items, train_idxs, trial)
                if s > best_score + 1e-6:
                    best_score = s
                    current[c] = (bw, round(1.0 - bw, 2))
                    changed = True
        if not changed:
            break
    return current, best_score


def main() -> None:
    items = precompute_raw()
    print(f"\n{len(items)} scored queries ready")

    folds = stratified_kfold(items, N_FOLDS, SEED)
    print(f"folds sizes: {[len(f) for f in folds]}")

    # Baseline (untuned) held-out per fold
    baseline = deepcopy(WEIGHTS)
    base_all, _ = ndcg_on_subset(items, list(range(len(items))), baseline)
    print(f"\nbaseline (WEIGHTS) on all {len(items)}: nDCG@10 = {base_all:.4f}")

    per_fold = []
    held_ndcgs_baseline = []
    held_ndcgs_tuned = []
    for k in range(N_FOLDS):
        held = folds[k]
        train = [i for j in range(N_FOLDS) if j != k for i in folds[j]]
        print(f"\n=== fold {k+1}/{N_FOLDS}  train={len(train)} held={len(held)} ===")
        tuned, train_score = coord_descent(items, train, init=baseline, passes=2)
        train_base, _ = ndcg_on_subset(items, train, baseline)
        held_base, _ = ndcg_on_subset(items, held, baseline)
        held_tuned, held_by_cls = ndcg_on_subset(items, held, tuned)
        print(f"  train baseline -> tuned: {train_base:.4f} -> {train_score:.4f}")
        print(f"  held  baseline -> tuned: {held_base:.4f} -> {held_tuned:.4f}   Δ={held_tuned - held_base:+.4f}")
        print(f"  tuned weights: {{{', '.join(f'{c}:{w[0]:.1f}' for c, w in tuned.items())}}}")
        per_fold.append({
            "fold": k,
            "n_train": len(train), "n_held": len(held),
            "train_baseline": train_base, "train_tuned": train_score,
            "held_baseline": held_base, "held_tuned": held_tuned,
            "tuned_weights": {c: list(v) for c, v in tuned.items()},
            "held_ndcg_by_class": held_by_cls,
        })
        held_ndcgs_baseline.append(held_base)
        held_ndcgs_tuned.append(held_tuned)

    # Generalization estimates
    gen_base = float(np.mean(held_ndcgs_baseline))
    gen_tuned = float(np.mean(held_ndcgs_tuned))

    # Tune on all data (for comparison with per-fold)
    all_idx = list(range(len(items)))
    tuned_all, tuned_all_score = coord_descent(items, all_idx, init=baseline, passes=2)
    print(f"\n=== OVERFIT ANALYSIS ===")
    print(f"baseline on all 149:            nDCG@10 = {base_all:.4f}")
    print(f"tuned-on-all-149 (IN-SAMPLE):   nDCG@10 = {tuned_all_score:.4f}  (+{tuned_all_score - base_all:.4f})")
    print(f"baseline 3-fold held-out avg:   nDCG@10 = {gen_base:.4f}")
    print(f"tuned    3-fold held-out avg:   nDCG@10 = {gen_tuned:.4f}  (+{gen_tuned - gen_base:.4f} vs baseline held-out)")
    print(f"overfit gap (in-sample - held): nDCG@10   {tuned_all_score - gen_tuned:+.4f}")

    OUT_PATH.write_text(json.dumps({
        "n_queries": len(items),
        "n_folds": N_FOLDS,
        "seed": SEED,
        "baseline_weights": {c: list(v) for c, v in baseline.items()},
        "tuned_all_weights": {c: list(v) for c, v in tuned_all.items()},
        "tuned_all_ndcg@10_in_sample": tuned_all_score,
        "baseline_ndcg@10_all": base_all,
        "generalization": {
            "baseline_held_out_avg": gen_base,
            "tuned_held_out_avg": gen_tuned,
            "overfit_gap_ndcg@10": tuned_all_score - gen_tuned,
        },
        "per_fold": per_fold,
    }, indent=2))
    print(f"\nsaved -> {OUT_PATH}")


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    main()
