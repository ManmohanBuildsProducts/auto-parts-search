"""Upload listwise training data to HF Hub as a private dataset.

Usage:
    python3.11 -m scripts.upload_listwise_to_hf
"""
from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from huggingface_hub import HfApi

SRC = Path("data/training/experiments/2026-04-22-cadet/listwise_scored.jsonl")
REPO = "ManmohanBuildsProducts/auto-parts-listwise-v1"


def main() -> None:
    records = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    print(f"loaded {len(records)} records")

    flat = []
    for rec in records:
        flat.append({
            "query": rec["query"],
            "query_type": rec["query_type"],
            "gold_doc_id": rec["gold_doc_id"],
            "gold_doc_title": rec["gold_doc_title"],
            "candidate_doc_ids": json.dumps([c["doc_id"] for c in rec["candidates"]]),
            "candidate_doc_titles": json.dumps([c["doc_title"] for c in rec["candidates"]]),
            "teacher_scores": json.dumps([c["teacher_score"] for c in rec["candidates"]]),
        })

    HfApi().create_repo(repo_id=REPO, repo_type="dataset", private=True, exist_ok=True)
    ds = Dataset.from_list(flat)
    ds.push_to_hub(REPO, private=True, commit_message="listwise v1 — 5K catalog docs, bge-reranker-v2-m3 teacher")
    print(f"pushed {len(flat)} rows → https://huggingface.co/datasets/{REPO}")


if __name__ == "__main__":
    main()
