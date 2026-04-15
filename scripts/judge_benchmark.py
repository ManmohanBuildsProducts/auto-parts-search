"""T208b — Expand benchmark ground truth to graded top-20 labels via LLM judge.

For each query in benchmark_dev.json:
  1. Retrieve top-20 candidate parts from the KG corpus via the best
     current model (v1.2 — ManmohanBuildsProducts/auto-parts-search-v1).
  2. Ask DeepSeek R1 (deepseek-reasoner) to grade each candidate:
       2 = relevant       (clear match for the query intent)
       1 = marginal       (related but not what user wants)
       0 = irrelevant     (wrong part)
  3. Save query + candidates + graded labels to JSON.

Output is incremental — each query appended to a JSONL as it completes,
so a crash/ctrl-C loses at most one query.

Usage:
    export DEEPSEEK_API_KEY=sk-...
    python3.11 -m scripts.judge_benchmark \
        --benchmark data/training/golden/benchmark_dev.json \
        --model ManmohanBuildsProducts/auto-parts-search-v1 \
        --out data/training/experiments/2026-04-13-graded/benchmark_dev_graded.jsonl
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

GRAPH_DB = Path("data/knowledge_graph/graph.db")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"

JUDGE_SYSTEM = """You are an expert Indian auto-parts mechanic grading search relevance for an auto-parts e-commerce search engine. You understand Hindi/Hinglish ("patti" = brake pad, "kicker" = kick starter, "silencer" = muffler), symptom-based queries ("engine garam" = engine overheating), brand-as-generic usage ("Mobil" = any engine oil), misspellings ("break pad" for "brake pad"), and part numbers.

For each candidate part, judge its relevance to the user's search query. Return ONLY a JSON array of integer grades (no prose, no markdown fences):
  2 = RELEVANT: this part is clearly what the query is asking for (direct match, correct synonym, or the exact part that fixes the described symptom).
  1 = MARGINAL: related to the query (same system, adjacent part, or a component of what they want) but not the direct answer.
  0 = IRRELEVANT: wrong part entirely.

The array length MUST equal the number of candidates. Example output:
[2, 1, 0, 0, 2, 1, 0, 0, 0, 0, 1, 0, 0, 0, 2, 0, 0, 0, 0, 1]"""


def load_corpus(db_path: Path):
    from training.evaluate import load_corpus as _lc
    return _lc(db_path)


def retrieve_top_k(model_path: str, queries: list[str], docs: list[str], k: int) -> np.ndarray:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(model_path, trust_remote_code=True)
    doc_emb = model.encode(docs, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    q_emb = model.encode(queries, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=True)
    sims = q_emb @ doc_emb.T
    return np.argsort(-sims, axis=1)[:, :k]


def judge_with_deepseek(query: str, candidates: list[str], api_key: str, model: str = "deepseek-reasoner") -> list[int]:
    import urllib.request
    numbered = "\n".join(f"{i+1}. {c}" for i, c in enumerate(candidates))
    user_msg = f"Query: {query}\n\nCandidates:\n{numbered}\n\nReturn the {len(candidates)}-element grade array."

    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        "temperature": 0.0,
        "max_tokens": 8000,
    }).encode("utf-8")

    req = urllib.request.Request(
        DEEPSEEK_URL, data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                payload = json.loads(resp.read())
            content = payload["choices"][0]["message"]["content"].strip()
            # Strip code fences if the model ignored instructions
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content.split("\n", 1)[1].strip()
            grades = json.loads(content)
            if len(grades) != len(candidates):
                raise ValueError(f"judge returned {len(grades)} grades for {len(candidates)} candidates")
            if not all(g in (0, 1, 2) for g in grades):
                raise ValueError(f"invalid grade values: {grades}")
            return grades
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default="data/training/golden/benchmark_dev.json")
    ap.add_argument("--model", action="append", default=None,
                    help="Model repo. Repeat for a joint pool (union of each model's top-k).")
    ap.add_argument("--out", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--deepseek-model", default="deepseek-reasoner")
    args = ap.parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: set DEEPSEEK_API_KEY", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Resume support — skip queries already judged.
    done_queries: set[str] = set()
    if out_path.exists():
        for line in out_path.read_text().splitlines():
            if line.strip():
                done_queries.add(json.loads(line)["query"])
        print(f"resuming — {len(done_queries)} queries already judged")

    benchmark = json.loads(Path(args.benchmark).read_text())
    part_ids, docs, _ = load_corpus(GRAPH_DB)

    to_do = [q for q in benchmark if q["query"] not in done_queries]
    print(f"queries to judge: {len(to_do)}/{len(benchmark)} (k={args.k})")
    if not to_do:
        print("nothing to do.")
        return

    # Retrieve top-k per model. When multiple models are given, union the
    # per-query top-k across models (dedup, preserve one-model-rank as tiebreak).
    models = args.model or ["ManmohanBuildsProducts/auto-parts-search-v1"]
    queries = [q["query"] for q in to_do]
    all_top_k = [retrieve_top_k(m, queries, docs, args.k) for m in models]

    # For each query, build ordered union of indices across models.
    unioned: list[list[int]] = []
    for qi in range(len(to_do)):
        seen: set[int] = set()
        order: list[int] = []
        for mi in range(len(models)):
            for idx in all_top_k[mi][qi]:
                idx_i = int(idx)
                if idx_i not in seen:
                    seen.add(idx_i)
                    order.append(idx_i)
        unioned.append(order)

    with out_path.open("a") as f:
        for qi, q in enumerate(to_do):
            idxs = unioned[qi]
            candidates = [docs[i] for i in idxs]
            candidate_ids = [part_ids[i] for i in idxs]

            print(f"[{qi+1}/{len(to_do)}] ({q['query_type']}) {q['query'][:60]}", flush=True)
            try:
                grades = judge_with_deepseek(q["query"], candidates, api_key, args.deepseek_model)
            except Exception as e:
                print(f"  SKIPPED: {e}", file=sys.stderr)
                continue

            rec = {
                "query": q["query"],
                "query_type": q["query_type"],
                "difficulty": q.get("difficulty"),
                "expected_parts": q.get("expected_parts", []),
                "candidate_ids": candidate_ids,
                "candidate_docs": candidates,
                "grades": grades,
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()

            rel = sum(1 for g in grades if g == 2)
            mar = sum(1 for g in grades if g == 1)
            print(f"   -> n={len(grades)}: {rel} rel, {mar} marginal, {len(grades) - rel - mar} irr", flush=True)

    print(f"\nsaved -> {out_path}")


if __name__ == "__main__":
    main()
