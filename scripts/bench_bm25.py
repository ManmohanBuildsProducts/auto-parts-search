"""Benchmark BM25 on the 149-query dev set.

Reuses the same substring-match relevance as training.evaluate so the
BM25 numbers are directly comparable to v3's binary-eval baseline.

Output:
  data/training/experiments/2026-04-14-v5/bm25-dev.json

Usage:
    python3 -m scripts.bench_bm25
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

from auto_parts_search.search_bm25 import search
from auto_parts_search.tokenizer import BridgeTransliterator, IndicTokenizer, SarvamTransliterator


def dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="data/training/golden/benchmark_dev.json")
    ap.add_argument("--out", default="data/training/experiments/2026-04-14-v5/bm25-dev.json")
    ap.add_argument("--k-ndcg", type=int, default=10)
    ap.add_argument("--k-recall", type=int, default=5)
    ap.add_argument("--sarvam", action="store_true")
    args = ap.parse_args()

    # Load corpus relevance strings (name + aliases per part) for substring match
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

    # Tokenizer
    if args.sarvam:
        tok = IndicTokenizer(transliterator=BridgeTransliterator(sarvam=SarvamTransliterator()))
    else:
        tok = IndicTokenizer()

    benchmark = json.loads(Path(args.benchmark).read_text())

    def is_relevant(expected_parts: list[str], part_id: str) -> bool:
        strs = rel_strings.get(part_id, set())
        for ep in expected_parts:
            epl = ep.lower().strip()
            if not epl:
                continue
            for rs in strs:
                if epl in rs or rs in epl:
                    return True
        return False

    rrs: list[float] = []
    ndcgs: list[float] = []
    recalls: list[float] = []
    zero_by_type: dict[str, list[int]] = defaultdict(list)

    for qi, q in enumerate(benchmark):
        hits = search(q["query"], k=max(args.k_ndcg, args.k_recall, 20), tokenizer=tok)
        expected = q.get("expected_parts", [])
        rels = [1 if is_relevant(expected, h.part_id) else 0 for h in hits]

        # MRR
        rr = 0.0
        for rank, r in enumerate(rels, start=1):
            if r:
                rr = 1.0 / rank
                break
        rrs.append(rr)

        # nDCG@k binary
        top = rels[: args.k_ndcg]
        ideal = sorted(top, reverse=True)
        denom = dcg(ideal) or 1.0
        ndcgs.append(dcg(top) / denom)

        # Recall@k
        total_rel = sum(rels)
        recalls.append(sum(rels[: args.k_recall]) / total_rel if total_rel else 0.0)

        qt = q.get("query_type", "unknown")
        zero_by_type[qt].append(0 if sum(rels[:10]) else 1)

    n = len(benchmark)
    result = {
        "model": "bm25_meilisearch",
        "benchmark": args.benchmark,
        "n_queries": n,
        "corpus_size": len(rel_strings),
        "mrr": sum(rrs) / n,
        f"ndcg@{args.k_ndcg}": sum(ndcgs) / n,
        f"recall@{args.k_recall}": sum(recalls) / n,
        "zero_result_rate_by_type": {
            qt: {"rate": sum(v) / len(v), "n": len(v)} for qt, v in sorted(zero_by_type.items())
        },
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
