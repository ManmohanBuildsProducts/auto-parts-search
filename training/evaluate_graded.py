"""T208b follow-on — Graded evaluator using LLM-judged ground truth.

Loads benchmark_dev_graded.jsonl (from scripts/judge_benchmark.py) which
has, per query, the v1.2-retrieved top-20 candidates with human-quality
0/1/2 grades. Re-scores any model against the SAME candidate pool using
those grades, yielding a fair nDCG@10 comparison.

Important: this only measures quality within the top-20 pool v1.2 surfaced.
A model that would retrieve a completely different top-20 may be unfairly
scored — but for the models we're comparing (BGE-m3 vs v1.2), there's
heavy overlap in the top-20, so this is still a meaningful metric.

Metrics:
  - graded nDCG@10 (gains 0/1/2)
  - graded Recall@5 (fraction of RELEVANT=2 items in top-5)
  - pool-overlap (how much of the judged pool the model ranks in top-20)

Usage:
    python3 -m training.evaluate_graded \
        --model BAAI/bge-m3 \
        --graded data/training/experiments/2026-04-13-graded/benchmark_dev_graded.jsonl \
        --out data/training/experiments/2026-04-13-graded/bge-m3-graded.json
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from training.evaluate import GRAPH_DB, load_corpus


def dcg(rels: list[float]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--graded", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--k-ndcg", type=int, default=10)
    ap.add_argument("--k-recall", type=int, default=5)
    ap.add_argument("--query-prefix", default="")
    ap.add_argument("--doc-prefix", default="")
    args = ap.parse_args()

    from sentence_transformers import SentenceTransformer

    graded = [json.loads(l) for l in Path(args.graded).read_text().splitlines() if l.strip()]
    print(f"loaded {len(graded)} graded queries")

    part_ids, docs, _ = load_corpus(GRAPH_DB)
    id_to_idx = {pid: i for i, pid in enumerate(part_ids)}

    # Sanity: judged candidate_ids must all be known parts
    for g in graded[:5]:
        for cid in g["candidate_ids"]:
            assert cid in id_to_idx, f"unknown part id: {cid}"

    model = SentenceTransformer(args.model, trust_remote_code=True)
    doc_texts = [(args.doc_prefix + d) for d in docs] if args.doc_prefix else docs
    doc_emb = model.encode(doc_texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    queries = [(args.query_prefix + g["query"]) for g in graded]
    q_emb = model.encode(queries, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)

    sims = q_emb @ doc_emb.T  # (Q, D)

    ndcgs: list[float] = []
    recalls: list[float] = []
    overlaps: list[float] = []
    ndcg_by_type: dict[str, list[float]] = defaultdict(list)

    for qi, g in enumerate(graded):
        cand_ids = g["candidate_ids"]
        grades = g["grades"]
        id_to_grade = dict(zip(cand_ids, grades))
        judged_idxs = {id_to_idx[cid] for cid in cand_ids}

        # This model's ranking over the full corpus.
        full_order = np.argsort(-sims[qi])

        # For metrics, rescore each position by the judged grade (0 if not judged).
        top_n = full_order[:max(args.k_ndcg, args.k_recall, 20)]
        grade_sequence = [id_to_grade.get(part_ids[i], 0) for i in top_n]

        # nDCG@k with graded gains (ideal DCG computed over ALL judged grades).
        gains_at_k = grade_sequence[: args.k_ndcg]
        ideal_gains = sorted(grades, reverse=True)[: args.k_ndcg]
        idcg = dcg(ideal_gains) or 1.0
        ndcg = dcg(gains_at_k) / idcg
        ndcgs.append(ndcg)
        ndcg_by_type[g["query_type"]].append(ndcg)

        # Recall@k — fraction of RELEVANT (grade 2) items found in top-k.
        total_rel = sum(1 for gr in grades if gr == 2)
        if total_rel:
            found = sum(1 for x in grade_sequence[: args.k_recall] if x == 2)
            recalls.append(found / total_rel)
        else:
            recalls.append(0.0)

        # Pool overlap: how many of the judged 20 does this model rank in its top-20?
        top_20_set = set(int(i) for i in full_order[:20])
        overlaps.append(len(top_20_set & judged_idxs) / 20.0)

    result = {
        "model": args.model,
        "graded": str(args.graded),
        "n_queries": len(graded),
        f"graded_ndcg@{args.k_ndcg}": float(np.mean(ndcgs)),
        f"graded_recall@{args.k_recall}": float(np.mean(recalls)),
        "pool_overlap": float(np.mean(overlaps)),
        f"graded_ndcg@{args.k_ndcg}_by_type": {
            t: {"score": float(np.mean(v)), "n": len(v)}
            for t, v in sorted(ndcg_by_type.items())
        },
    }

    print(json.dumps(result, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
