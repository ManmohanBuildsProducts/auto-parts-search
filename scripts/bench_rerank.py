"""T601 — Apply LLM re-ranker to top-20 from tuned hybrid, re-score vs judged pool.

Produces the `v3+bm25-hybrid-tuned+rerank` scoreboard row.

Pipeline per query:
    hybrid-tuned top-20  →  LLM re-rank  →  new top-10 order

Saves:
    round2_rerank_rankings.json — reranked top-20 per query, resumable
    rerank_scores.json          — metrics vs round2 judged pool

Resume: the orchestrator appends to a JSONL sidecar per query and skips
queries already done on re-run. Crash-safe.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from auto_parts_search.rerank import rerank, RerankerConfig

ROUND_DIR = Path("data/training/experiments/2026-04-15-bench-production")
CORPUS_PATH = ROUND_DIR / "round2_corpus.json"
GRADED_PATH = ROUND_DIR / "round2_graded.jsonl"
BENCHMARK_PATH = Path("data/training/golden/benchmark_dev.json")
TUNED_RANKS_PATH = ROUND_DIR / "round2_hybrid_rankings_tuned.json"

RERANK_JSONL = ROUND_DIR / "round2_rerank_rankings.jsonl"
RERANK_JSON = ROUND_DIR / "round2_rerank_rankings.json"
RERANK_SCORES = ROUND_DIR / "rerank_scores.json"


def dcg(rels): return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ap_at_k(rels_bin, k):
    hits = 0; s = 0.0
    for i, r in enumerate(rels_bin[:k]):
        if r:
            hits += 1
            s += hits / (i + 1)
    tot = sum(1 for r in rels_bin if r)
    return (s / min(tot, k)) if tot else 0.0


def phase_rerank() -> None:
    """Apply rerank to tuned-hybrid top-20 for all 149 queries. Resumable."""
    corpus = json.loads(CORPUS_PATH.read_text())
    id_to_text = dict(zip(corpus["ids"], corpus["texts"]))

    tuned = json.loads(TUNED_RANKS_PATH.read_text())
    q_to_ranking = dict(zip(tuned["queries"], tuned["rankings"]))

    done: set[str] = set()
    if RERANK_JSONL.exists():
        for line in RERANK_JSONL.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["query"])
        print(f"resume: {len(done)}/{len(q_to_ranking)} queries already reranked")

    to_do = [q for q in tuned["queries"] if q not in done]
    print(f"reranking {len(to_do)} queries...")
    cfg = RerankerConfig(model="deepseek-chat", temperature=0.0)

    t0 = time.time()
    with RERANK_JSONL.open("a") as f:
        for qi, q in enumerate(to_do):
            ids20 = q_to_ranking[q]
            docs20 = [id_to_text.get(pid, pid) for pid in ids20]
            t_q = time.time()
            try:
                ranked_ids = rerank(q, ids20, docs20, cfg)
            except Exception as e:
                print(f"[{qi+1}/{len(to_do)}] FALLBACK ({e}): {q[:50]}", file=sys.stderr)
                ranked_ids = ids20  # passthrough
            elapsed = time.time() - t_q
            rec = {"query": q, "reranked_ids": ranked_ids, "elapsed_sec": elapsed}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            if (qi + 1) % 10 == 0 or qi < 5:
                print(f"  [{qi+1}/{len(to_do)}] {elapsed:.1f}s  '{q[:55]}'", flush=True)
    dt = (time.time() - t0) / 60
    print(f"\nrerank done in {dt:.1f} min -> {RERANK_JSONL}")

    # Consolidate into single JSON (format matching hybrid_rankings)
    records = [json.loads(l) for l in RERANK_JSONL.read_text().splitlines() if l.strip()]
    out = {
        "queries": [r["query"] for r in records],
        "rankings": [r["reranked_ids"] for r in records],
        "latencies_sec": [r["elapsed_sec"] for r in records],
    }
    RERANK_JSON.write_text(json.dumps(out, ensure_ascii=False))
    latencies = [r["elapsed_sec"] for r in records]
    print(f"latency p50={np.median(latencies):.2f}s p95={np.percentile(latencies, 95):.2f}s mean={np.mean(latencies):.2f}s")
    print(f"saved -> {RERANK_JSON}")


def phase_score() -> dict:
    """Score the rerank row vs round2 judged pool. Same metric suite as bench_production."""
    bench = json.loads(BENCHMARK_PATH.read_text())
    graded = [json.loads(l) for l in GRADED_PATH.read_text().splitlines() if l.strip()]
    q_to_grade = {g["query"]: g for g in graded}

    rr = json.loads(RERANK_JSON.read_text())
    q_to_ranking = dict(zip(rr["queries"], rr["rankings"]))

    ndcgs = []; recalls5 = []; p1 = []; maps = []; z = 0
    ndcg_by_type: dict[str, list[float]] = defaultdict(list)
    for q in bench:
        if q["query"] not in q_to_grade or q["query"] not in q_to_ranking:
            continue
        g = q_to_grade[q["query"]]
        id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))
        ranked_ids = q_to_ranking[q["query"]]
        grade_seq = [id_to_grade.get(pid, 0) for pid in ranked_ids[:20]]
        while len(grade_seq) < 20:
            grade_seq.append(0)

        gains_10 = grade_seq[:10]
        ideal = sorted(g["grades"], reverse=True)[:10]
        idcg = dcg(ideal) or 1.0
        ndcg = dcg(gains_10) / idcg
        ndcgs.append(ndcg)
        ndcg_by_type[q["query_type"]].append(ndcg)

        total_rel = sum(1 for gr in g["grades"] if gr == 2)
        if total_rel:
            recalls5.append(sum(1 for x in grade_seq[:5] if x == 2) / total_rel)
        else:
            recalls5.append(0.0)

        p1.append(1.0 if grade_seq[0] >= 1 else 0.0)
        rels_bin = [1 if gr >= 1 else 0 for gr in grade_seq]
        maps.append(ap_at_k(rels_bin, 10))
        if not any(gr >= 1 for gr in grade_seq[:10]):
            z += 1

    metrics = {
        "ndcg@10_graded": float(np.mean(ndcgs)),
        "recall@5_graded": float(np.mean(recalls5)),
        "p@1": float(np.mean(p1)),
        "map@10": float(np.mean(maps)),
        "zero_result_rate@10": z / max(1, len(ndcgs)),
        "n_scored": len(ndcgs),
        "ndcg@10_by_type": {t: {"score": float(np.mean(v)), "n": len(v)} for t, v in sorted(ndcg_by_type.items())},
    }
    print("\nv3+bm25-hybrid-tuned+rerank:")
    print(f"  nDCG@10 = {metrics['ndcg@10_graded']:.3f}")
    print(f"  R@5     = {metrics['recall@5_graded']:.3f}")
    print(f"  P@1     = {metrics['p@1']:.3f}")
    print(f"  MAP@10  = {metrics['map@10']:.3f}")
    print(f"  0-result% = {metrics['zero_result_rate@10']*100:.1f}")
    print("\nper-category nDCG@10:")
    for t, v in metrics["ndcg@10_by_type"].items():
        print(f"  {t:24s} {v['score']:.3f} (n={v['n']})")

    RERANK_SCORES.write_text(json.dumps(metrics, indent=2))
    print(f"\nsaved -> {RERANK_SCORES}")
    return metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["rerank", "score", "all"])
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    if args.phase in ("rerank", "all"):
        phase_rerank()
    if args.phase in ("score", "all"):
        phase_score()


if __name__ == "__main__":
    main()
