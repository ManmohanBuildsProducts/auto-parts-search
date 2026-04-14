"""Benchmark hybrid retrieval on dev-149 (binary substring match + save joint pool)."""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

from auto_parts_search.search_hybrid import search as hybrid_search


def dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="data/training/golden/benchmark_dev.json")
    ap.add_argument("--out", default="data/training/experiments/2026-04-14-v5/hybrid-dev.json")
    ap.add_argument("--out-pool", default="data/training/experiments/2026-04-14-v5/hybrid-top20.jsonl")
    args = ap.parse_args()

    # relevance strings per part
    conn = sqlite3.connect("data/knowledge_graph/graph.db")
    rel_strings: dict[str, set[str]] = {}
    for pid, name in conn.execute("SELECT id, name FROM nodes WHERE type='part'"):
        rel_strings[pid] = {name.lower()}
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias'"
    ):
        rel_strings.setdefault(part_id, set()).add(alias_name.lower())
    conn.close()

    def is_relevant(expected: list[str], pid: str) -> bool:
        strs = rel_strings.get(pid, set())
        for ep in expected:
            epl = ep.lower().strip()
            if not epl:
                continue
            for rs in strs:
                if epl in rs or rs in epl:
                    return True
        return False

    benchmark = json.loads(Path(args.benchmark).read_text())
    rrs, ndcgs, recalls = [], [], []
    zero_by_type: dict[str, list[int]] = defaultdict(list)
    pool_rows: list[dict] = []

    for q in benchmark:
        hits = hybrid_search(q["query"], k=20, k_candidates=30)
        rels = [1 if is_relevant(q.get("expected_parts", []), h.part_id) else 0 for h in hits]
        rr = 0.0
        for rank, r in enumerate(rels, 1):
            if r:
                rr = 1.0 / rank
                break
        rrs.append(rr)
        top = rels[:10]
        ideal = sorted(top, reverse=True)
        ndcgs.append(dcg(top) / (dcg(ideal) or 1.0))
        tot = sum(rels)
        recalls.append(sum(rels[:5]) / tot if tot else 0.0)
        qt = q.get("query_type", "unknown")
        zero_by_type[qt].append(0 if sum(rels[:10]) else 1)

        pool_rows.append({
            "query": q["query"],
            "query_type": qt,
            "difficulty": q.get("difficulty"),
            "expected_parts": q.get("expected_parts", []),
            "candidate_ids": [h.part_id for h in hits],
            "candidate_docs": [h.name for h in hits],
        })

    n = len(benchmark)
    result = {
        "model": "hybrid_bm25_v3_rrf",
        "benchmark": args.benchmark,
        "n_queries": n,
        "mrr": sum(rrs) / n,
        "ndcg@10": sum(ndcgs) / n,
        "recall@5": sum(recalls) / n,
        "zero_result_rate_by_type": {qt: {"rate": sum(v)/len(v), "n": len(v)} for qt, v in sorted(zero_by_type.items())},
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    with Path(args.out_pool).open("w") as f:
        for r in pool_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
