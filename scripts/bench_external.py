"""T305 round 1 — external embedding benchmark orchestrator.

Phases:
  A. embed     - compute corpus+query embeddings for all 6 models (cached)
  B. pool      - build joint pool (union of top-20 per model) per query
  C. judge     - LLM-grade joint pool via DeepSeek (reuses scripts.judge_benchmark)
  D. score     - compute metrics for each model against judged pool
  E. report    - emit markdown table + JSON

Split invocation so we can checkpoint between pool (cheap) and judge (expensive):

    python3 -m scripts.bench_external embed
    python3 -m scripts.bench_external pool
    python3 -m scripts.bench_external judge
    python3 -m scripts.bench_external score
    python3 -m scripts.bench_external report
    python3 -m scripts.bench_external all    # runs everything in order
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

from scripts._embed_api import MODELS, embed

ROUND = "round1"
OUT_DIR = Path("data/training/experiments/2026-04-15-bench-external")
OUT_DIR.mkdir(parents=True, exist_ok=True)

CORPUS_DOCS_PATH = Path("data/external/processed/v3_corpus_docs.json")
CORPUS_IDS_PATH = Path("data/external/processed/v3_corpus_part_ids.json")
BENCHMARK_PATH = Path("data/training/golden/benchmark_dev.json")

POOL_PATH = OUT_DIR / f"{ROUND}_joint_pool.json"
GRADED_PATH = OUT_DIR / f"{ROUND}_graded.jsonl"
SCORES_PATH = OUT_DIR / f"{ROUND}_scores.json"
HYBRID_RANKS_PATH = OUT_DIR / f"{ROUND}_hybrid_rankings.json"
REPORT_PATH = Path("docs/eval_round1.md")

TOPK_POOL = 20  # top-k per model fed into joint pool

SANITY_QUERIES = ["brake pad", "spark plug", "engine oil"]


def load_inputs() -> tuple[list[str], list[str], list[dict]]:
    docs = json.loads(CORPUS_DOCS_PATH.read_text())
    ids = json.loads(CORPUS_IDS_PATH.read_text())
    bench = json.loads(BENCHMARK_PATH.read_text())
    assert len(docs) == len(ids)
    return ids, docs, bench


# --- Phase A: embed ---

def phase_embed() -> dict[str, dict]:
    ids, docs, bench = load_inputs()
    queries = [b["query"] for b in bench]
    print(f"corpus: {len(docs)} docs | queries: {len(queries)}\n")
    out = {}
    for mk in MODELS:
        print(f"--- {mk} ---")
        t0 = time.time()
        d_emb = embed(mk, docs, role="doc")
        q_emb = embed(mk, queries, role="query")
        out[mk] = {"d_emb": d_emb, "q_emb": q_emb, "elapsed": time.time() - t0}
        print(f"  -> d={d_emb.shape} q={q_emb.shape} in {out[mk]['elapsed']:.1f}s\n")
    return out


# --- Phase B: pool ---

def phase_pool(embeds: dict[str, dict] | None = None) -> dict:
    """Build joint pool per query + sanity-check 3 canonical queries."""
    ids, docs, bench = load_inputs()
    if embeds is None:
        embeds = phase_embed()

    # For each query, collect top-k indices per model.
    per_model_topk: dict[str, np.ndarray] = {}  # (Q, K)
    per_model_top1: dict[str, list[str]] = {}   # for sanity

    queries = [b["query"] for b in bench]
    for mk, e in embeds.items():
        sims = e["q_emb"] @ e["d_emb"].T  # (Q, D)
        top = np.argsort(-sims, axis=1)[:, :TOPK_POOL]
        per_model_topk[mk] = top
        per_model_top1[mk] = [ids[top[qi, 0]] for qi in range(len(queries))]

    # Union per query, preserving first-seen order
    joint_pool: list[list[int]] = []
    sizes = []
    for qi in range(len(queries)):
        seen = set()
        order = []
        for mk in MODELS:
            for idx in per_model_topk[mk][qi]:
                i = int(idx)
                if i not in seen:
                    seen.add(i)
                    order.append(i)
        joint_pool.append(order)
        sizes.append(len(order))

    # Save
    pool_data = {
        "round": ROUND,
        "corpus_size": len(docs),
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
                "pool_docs": [docs[i] for i in joint_pool[qi]],
            }
            for qi in range(len(queries))
        ],
    }
    POOL_PATH.write_text(json.dumps(pool_data, ensure_ascii=False))
    print(f"\npool sizes: min={min(sizes)} median={int(np.median(sizes))} max={max(sizes)} mean={np.mean(sizes):.1f}")
    print(f"saved -> {POOL_PATH}")

    # Sanity: print top-5 per model for 3 canonical queries
    print("\n=== SANITY CHECK (top-5 per model on canonical queries) ===")
    for sq in SANITY_QUERIES:
        print(f"\n  query: '{sq}'")
        # encode this one-off for sanity (use cache if matched)
        for mk in MODELS:
            e = embeds[mk]
            # Find if query is in bench (likely not, so embed 1-off)
            q = embed(mk, [sq], role="query", use_cache=True)[0]
            sims = e["d_emb"] @ q
            top5 = np.argsort(-sims)[:5]
            docs_short = [docs[i][:60] for i in top5]
            print(f"    {mk:18s}: {docs_short[0]}")
            for ds in docs_short[1:]:
                print(f"    {'':18s}  {ds}")
    return pool_data


# --- Phase C: judge ---

def phase_judge() -> None:
    pool = json.loads(POOL_PATH.read_text())
    ids, docs, _ = load_inputs()

    # Resume
    done = set()
    if GRADED_PATH.exists():
        for l in GRADED_PATH.read_text().splitlines():
            if l.strip():
                done.add(json.loads(l)["query"])
        print(f"resume: {len(done)}/{len(pool['per_query'])} queries already judged")

    from scripts.judge_benchmark import judge_with_deepseek
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY missing")

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
            print(f"   -> rel={rel} mar={mar} irr={len(grades)-rel-mar}")
    print(f"\ndone in {(time.time()-t0)/60:.1f} min -> {GRADED_PATH}")


# --- Phase C.5: hybrid rankings (H1) ---

def phase_hybrid() -> dict:
    """Compute v3+BM25 hybrid rankings over the same 2121-doc KG corpus.

    BM25 hits that fall outside the bench corpus are filtered out (fair scoring
    vs the joint-pool grades which only cover these 2121 docs).
    """
    from auto_parts_search.query_classifier import classify
    from auto_parts_search.search_bm25 import search as bm25_search
    from auto_parts_search.tokenizer import IndicTokenizer

    ids, docs, bench = load_inputs()
    id_set = set(ids)
    id_to_idx = {pid: i for i, pid in enumerate(ids)}

    # Use cached v3 embeddings for dense side.
    from scripts._embed_api import embed
    queries = [b["query"] for b in bench]
    v3_d = embed("v3-ours", docs, role="doc")
    v3_q = embed("v3-ours", queries, role="query")
    v3_sims = v3_q @ v3_d.T  # (Q, D)

    tok = IndicTokenizer()
    K_RRF = 60
    K_CAND = 30
    TOP = 20

    rankings: list[list[str]] = []
    classes: list[str] = []
    for qi, q in enumerate(bench):
        cls = classify(q["query"])
        classes.append(cls.query_class)

        # BM25 — fetch more than we need to account for catalog hits being filtered out.
        bm25_hits = bm25_search(q["query"], k=50, tokenizer=tok)
        bm25_ranks: dict[str, int] = {}
        rank = 0
        for h in bm25_hits:
            if h.part_id in id_set:
                rank += 1
                bm25_ranks[h.part_id] = rank
                if rank >= K_CAND:
                    break

        # Dense — v3 top-K over bench corpus
        emb_order = np.argsort(-v3_sims[qi])[:K_CAND]
        emb_ranks = {ids[int(i)]: r + 1 for r, i in enumerate(emb_order)}

        # RRF fusion with class weights
        all_ids = set(bm25_ranks) | set(emb_ranks)
        scores: dict[str, float] = {}
        for pid in all_ids:
            s = 0.0
            if pid in bm25_ranks:
                s += cls.bm25_weight / (K_RRF + bm25_ranks[pid])
            if pid in emb_ranks:
                s += cls.embedding_weight / (K_RRF + emb_ranks[pid])
            scores[pid] = s
        fused = sorted(scores.items(), key=lambda x: -x[1])[:TOP]
        rankings.append([pid for pid, _ in fused])

        if (qi + 1) % 30 == 0:
            print(f"  hybrid {qi+1}/{len(bench)}", flush=True)

    out = {
        "queries": [b["query"] for b in bench],
        "rankings": rankings,
        "classes": classes,
    }
    HYBRID_RANKS_PATH.write_text(json.dumps(out, ensure_ascii=False))
    print(f"saved -> {HYBRID_RANKS_PATH}")
    return out


# --- Phase D: score ---

def dcg(rels: list[float]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def ap_at_k(rels_binary: list[int], k: int) -> float:
    """Average precision at K with binary relevance (rel grade >= 1 counted)."""
    hits = 0
    s = 0.0
    for i, r in enumerate(rels_binary[:k]):
        if r:
            hits += 1
            s += hits / (i + 1)
    total_rel = sum(1 for r in rels_binary if r)
    if total_rel == 0:
        return 0.0
    return s / min(total_rel, k)


def phase_score(embeds: dict[str, dict] | None = None) -> dict:
    ids, docs, bench = load_inputs()
    id_to_idx = {pid: i for i, pid in enumerate(ids)}

    if embeds is None:
        # Re-load from cache by re-running embed (fast if cached)
        embeds = phase_embed()

    graded = [json.loads(l) for l in GRADED_PATH.read_text().splitlines() if l.strip()]
    q_to_grade = {g["query"]: g for g in graded}
    print(f"scoring against {len(graded)} judged queries")

    metrics_all = {}
    for mk in MODELS:
        q_emb = embeds[mk]["q_emb"]
        d_emb = embeds[mk]["d_emb"]
        sims = q_emb @ d_emb.T

        ndcgs = []
        recalls5 = []
        p1 = []
        maps = []
        ndcg_by_type: dict[str, list[float]] = defaultdict(list)
        z_count = 0  # zero-result rate @10 (no grade>=1 in top-10)

        for qi, q in enumerate(bench):
            if q["query"] not in q_to_grade:
                continue
            g = q_to_grade[q["query"]]
            id_to_grade = dict(zip(g["candidate_ids"], g["grades"]))

            full_order = np.argsort(-sims[qi])
            top20 = full_order[:20]
            grade_seq = [id_to_grade.get(ids[i], 0) for i in top20]

            # nDCG@10 (graded)
            gains_10 = grade_seq[:10]
            ideal = sorted(g["grades"], reverse=True)[:10]
            idcg = dcg(ideal) or 1.0
            ndcg = dcg(gains_10) / idcg
            ndcgs.append(ndcg)
            ndcg_by_type[q["query_type"]].append(ndcg)

            # Recall@5 (rel-grade-2 items)
            total_rel = sum(1 for gr in g["grades"] if gr == 2)
            if total_rel:
                found = sum(1 for x in grade_seq[:5] if x == 2)
                recalls5.append(found / total_rel)
            else:
                recalls5.append(0.0)

            # Precision@1: top-1 has grade >= 1
            p1.append(1.0 if grade_seq[0] >= 1 else 0.0)

            # MAP@10 (binary: grade>=1)
            rels_bin = [1 if gr >= 1 else 0 for gr in grade_seq]
            maps.append(ap_at_k(rels_bin, 10))

            # Zero-result@10
            if not any(gr >= 1 for gr in grade_seq[:10]):
                z_count += 1

        metrics_all[mk] = {
            "ndcg@10_graded": float(np.mean(ndcgs)) if ndcgs else 0.0,
            "recall@5_graded": float(np.mean(recalls5)) if recalls5 else 0.0,
            "p@1": float(np.mean(p1)) if p1 else 0.0,
            "map@10": float(np.mean(maps)) if maps else 0.0,
            "zero_result_rate@10": z_count / max(1, len(ndcgs)),
            "n_scored": len(ndcgs),
            "ndcg@10_by_type": {
                t: {"score": float(np.mean(v)), "n": len(v)}
                for t, v in sorted(ndcg_by_type.items())
            },
        }
        print(f"  {mk:18s}  nDCG@10={metrics_all[mk]['ndcg@10_graded']:.3f}  R@5={metrics_all[mk]['recall@5_graded']:.3f}  P@1={metrics_all[mk]['p@1']:.3f}  MAP@10={metrics_all[mk]['map@10']:.3f}")

    # --- Hybrid row (if computed) ---
    if HYBRID_RANKS_PATH.exists():
        h = json.loads(HYBRID_RANKS_PATH.read_text())
        q_to_ranking = dict(zip(h["queries"], h["rankings"]))
        ndcgs = []
        recalls5 = []
        p1 = []
        maps = []
        ndcg_by_type: dict[str, list[float]] = defaultdict(list)
        z_count = 0
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
                found = sum(1 for x in grade_seq[:5] if x == 2)
                recalls5.append(found / total_rel)
            else:
                recalls5.append(0.0)

            p1.append(1.0 if grade_seq[0] >= 1 else 0.0)
            rels_bin = [1 if gr >= 1 else 0 for gr in grade_seq]
            maps.append(ap_at_k(rels_bin, 10))
            if not any(gr >= 1 for gr in grade_seq[:10]):
                z_count += 1

        metrics_all["v3+bm25-hybrid"] = {
            "ndcg@10_graded": float(np.mean(ndcgs)) if ndcgs else 0.0,
            "recall@5_graded": float(np.mean(recalls5)) if recalls5 else 0.0,
            "p@1": float(np.mean(p1)) if p1 else 0.0,
            "map@10": float(np.mean(maps)) if maps else 0.0,
            "zero_result_rate@10": z_count / max(1, len(ndcgs)),
            "n_scored": len(ndcgs),
            "ndcg@10_by_type": {
                t: {"score": float(np.mean(v)), "n": len(v)}
                for t, v in sorted(ndcg_by_type.items())
            },
        }
        print(f"  v3+bm25-hybrid     nDCG@10={metrics_all['v3+bm25-hybrid']['ndcg@10_graded']:.3f}  R@5={metrics_all['v3+bm25-hybrid']['recall@5_graded']:.3f}  P@1={metrics_all['v3+bm25-hybrid']['p@1']:.3f}  MAP@10={metrics_all['v3+bm25-hybrid']['map@10']:.3f}")

    SCORES_PATH.write_text(json.dumps(metrics_all, indent=2))
    print(f"\nsaved -> {SCORES_PATH}")
    return metrics_all


# --- Phase E: report ---

def phase_report() -> None:
    scores = json.loads(SCORES_PATH.read_text())

    lines = []
    lines.append(f"# Eval — Round 1 (T305 external benchmark)\n")
    lines.append(f"Corpus: 2,121 KG docs (v3-ranked subset). Queries: 149 dev. Joint-pool judged by DeepSeek R1.\n")
    lines.append(f"Metric set: nDCG@10 (graded), Recall@5 (grade=2), P@1, MAP@10 (binary), zero-result@10 + per-category nDCG@10.\n")
    lines.append("## Overall scoreboard\n")
    lines.append("| Model | nDCG@10 | Recall@5 | P@1 | MAP@10 | 0-result% |")
    lines.append("|---|---:|---:|---:|---:|---:|")
    for mk, m in scores.items():
        lines.append(f"| `{mk}` | {m['ndcg@10_graded']:.3f} | {m['recall@5_graded']:.3f} | {m['p@1']:.3f} | {m['map@10']:.3f} | {m['zero_result_rate@10']*100:.1f}% |")

    # Per-category table
    types = sorted({t for m in scores.values() for t in m["ndcg@10_by_type"]})
    lines.append("\n## Per-category nDCG@10\n")
    header = "| Model | " + " | ".join(f"{t} (n={scores[list(scores)[0]]['ndcg@10_by_type'][t]['n']})" for t in types) + " |"
    lines.append(header)
    lines.append("|---" * (len(types) + 1) + "|")
    for mk, m in scores.items():
        row = [f"`{mk}`"] + [f"{m['ndcg@10_by_type'].get(t, {'score':0})['score']:.3f}" for t in types]
        lines.append("| " + " | ".join(row) + " |")

    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(f"report -> {REPORT_PATH}")
    print("\n".join(lines))


# --- CLI ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=["embed", "pool", "judge", "hybrid", "score", "report", "all"])
    args = ap.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    if args.phase == "embed":
        phase_embed()
    elif args.phase == "pool":
        phase_pool()
    elif args.phase == "judge":
        phase_judge()
    elif args.phase == "hybrid":
        phase_hybrid()
    elif args.phase == "score":
        phase_score()
    elif args.phase == "report":
        phase_report()
    elif args.phase == "all":
        embeds = phase_embed()
        phase_pool(embeds)
        phase_judge()
        phase_score(embeds)
        phase_report()


if __name__ == "__main__":
    main()
