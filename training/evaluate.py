"""T303a — Evaluation harness for embedding models.

Retrieval corpus: KG `part` nodes (name + aliases + parent system).
Relevance judgment: binary — a part is relevant if any `expected_parts`
string from the benchmark appears (case-insensitive substring) in the
part's name or aliases.

Metrics:
  - MRR (Mean Reciprocal Rank, first relevant hit across full ranking)
  - nDCG@10 (binary labels until T208b adds graded judgments)
  - Recall@5
  - zero_result_rate_by_type: fraction of queries per query_type with
    zero relevant hits in top-10.

Usage:
  python3 -m training.evaluate \
      --model all-MiniLM-L6-v2 \
      --benchmark data/training/golden/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import numpy as np

GRAPH_DB = Path("data/knowledge_graph/graph.db")


def load_corpus(db_path: Path = GRAPH_DB) -> tuple[list[str], list[str], list[set[str]]]:
    """Return (part_ids, doc_texts, relevance_strings_per_doc).

    relevance_strings_per_doc is the lowercased set of name + aliases used
    for matching expected_parts.
    """
    conn = sqlite3.connect(db_path)
    parts = list(conn.execute("SELECT id, name FROM nodes WHERE type='part'"))
    aliases: dict[str, list[str]] = defaultdict(list)
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e "
        "JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias'"
    ):
        aliases[part_id].append(alias_name)
    systems: dict[str, list[str]] = defaultdict(list)
    for part_id, sys_name in conn.execute(
        "SELECT e.src, n.name FROM edges e "
        "JOIN nodes n ON n.id = e.dst "
        "WHERE e.type='in_system' AND n.type='system'"
    ):
        systems[part_id].append(sys_name)
    conn.close()

    ids, docs, rel_strings = [], [], []
    for pid, name in parts:
        al = aliases.get(pid, [])
        sys = systems.get(pid, [])
        doc = name
        if al:
            doc += " | " + ", ".join(al)
        if sys:
            doc += " | system: " + ", ".join(sys)
        ids.append(pid)
        docs.append(doc)
        rel_strings.append({name.lower(), *(a.lower() for a in al)})
    return ids, docs, rel_strings


def is_relevant(expected_parts: list[str], rel_strings: set[str]) -> bool:
    for ep in expected_parts:
        epl = ep.lower().strip()
        if not epl:
            continue
        for rs in rel_strings:
            if epl in rs or rs in epl:
                return True
    return False


def dcg(rels: list[int]) -> float:
    return sum(r / math.log2(i + 2) for i, r in enumerate(rels))


def evaluate(
    model_path: str,
    benchmark_path: str | Path,
    db_path: Path = GRAPH_DB,
    k_ndcg: int = 10,
    k_recall: int = 5,
    k_zero: int = 10,
) -> dict:
    from sentence_transformers import SentenceTransformer

    benchmark = json.loads(Path(benchmark_path).read_text())
    part_ids, docs, rel_strings = load_corpus(db_path)

    model = SentenceTransformer(model_path)
    doc_emb = model.encode(docs, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    queries = [q["query"] for q in benchmark]
    q_emb = model.encode(queries, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)

    sims = q_emb @ doc_emb.T  # (Q, D), cosine since normalized

    rrs, ndcgs, recalls = [], [], []
    zero_by_type: dict[str, list[int]] = defaultdict(list)

    for qi, q in enumerate(benchmark):
        order = np.argsort(-sims[qi])
        expected = q.get("expected_parts", [])
        relevances = [1 if is_relevant(expected, rel_strings[d]) else 0 for d in order]

        # MRR (full)
        rr = 0.0
        for rank, r in enumerate(relevances, start=1):
            if r:
                rr = 1.0 / rank
                break
        rrs.append(rr)

        # nDCG@k (binary)
        top = relevances[:k_ndcg]
        ideal = sorted(top, reverse=True)
        denom = dcg(ideal) or 1.0
        ndcgs.append(dcg(top) / denom)

        # Recall@k — fraction of all relevant docs found in top-k
        total_rel = sum(relevances)
        if total_rel:
            recalls.append(sum(relevances[:k_recall]) / total_rel)
        else:
            recalls.append(0.0)

        # zero-result by query_type
        qt = q.get("query_type", "unknown")
        zero_by_type[qt].append(0 if sum(relevances[:k_zero]) else 1)

    return {
        "model": model_path,
        "benchmark": str(benchmark_path),
        "n_queries": len(benchmark),
        "corpus_size": len(part_ids),
        "mrr": float(np.mean(rrs)),
        f"ndcg@{k_ndcg}": float(np.mean(ndcgs)),
        f"recall@{k_recall}": float(np.mean(recalls)),
        "zero_result_rate_by_type": {
            qt: {"rate": sum(v) / len(v), "n": len(v)} for qt, v in sorted(zero_by_type.items())
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="all-MiniLM-L6-v2")
    ap.add_argument("--benchmark", default="data/training/golden/benchmark.json")
    ap.add_argument("--db", default=str(GRAPH_DB))
    ap.add_argument("--out", default=None, help="Optional path to write JSON results.")
    args = ap.parse_args()

    results = evaluate(args.model, args.benchmark, Path(args.db))
    print(json.dumps(results, indent=2))
    if args.out:
        Path(args.out).write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
