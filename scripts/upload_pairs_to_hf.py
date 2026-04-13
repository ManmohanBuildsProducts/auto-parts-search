"""Upload the v2 candidate pair set to a private HF Dataset.

Run this once locally. Colab notebook (notebooks/train_v1.ipynb) pulls
from here — avoids shipping a 5MB JSONL through the repo (experiments/
is gitignored per ADR 009) while still making the pairs reproducible.

Prereq: `huggingface-cli login` (or set HF_TOKEN env var).

Usage:
    python3 -m scripts.upload_pairs_to_hf
"""
from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from huggingface_hub import HfApi

SRC = Path("data/training/experiments/2026-04-13-kg-pairs/all_pairs_v2_candidate.jsonl")
REPO = "ManmohanBuildsProducts/auto-parts-search-pairs"


def main() -> None:
    records = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    print(f"loaded {len(records)} pairs from {SRC}")

    ds = Dataset.from_list(records)

    # Create repo if missing (idempotent)
    HfApi().create_repo(repo_id=REPO, repo_type="dataset", private=True, exist_ok=True)

    ds.push_to_hub(REPO, private=True, commit_message="v2 candidate pairs (2026-04-13 kg-pairs)")
    print(f"pushed to https://huggingface.co/datasets/{REPO} (private)")


if __name__ == "__main__":
    main()
