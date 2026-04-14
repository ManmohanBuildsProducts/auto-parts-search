"""Upload all three v4 variants to HF as separate private datasets.

Creates (or updates):
  ManmohanBuildsProducts/auto-parts-search-pairs-v4a
  ManmohanBuildsProducts/auto-parts-search-pairs-v4b
  ManmohanBuildsProducts/auto-parts-search-pairs-v4c

Usage:
    huggingface-cli login  (if not already)
    python3.11 -m scripts.upload_v4_variants
"""
from __future__ import annotations

import json
from pathlib import Path

from datasets import Dataset
from huggingface_hub import HfApi

SRC_DIR = Path("data/external/processed/v4_variants")
OWNER = "ManmohanBuildsProducts"


def main() -> None:
    api = HfApi()
    for variant in ("v4a", "v4b", "v4c"):
        fp = SRC_DIR / f"{variant}.jsonl"
        records = [json.loads(l) for l in fp.read_text().splitlines() if l.strip()]
        print(f"{variant}: {len(records)} records")

        ds = Dataset.from_list(records)
        repo = f"{OWNER}/auto-parts-search-pairs-{variant}"
        api.create_repo(repo_id=repo, repo_type="dataset", private=True, exist_ok=True)
        ds.push_to_hub(repo, private=True, commit_message=f"v4 ablation: {variant} ({len(records)} pairs)")
        print(f"  -> https://huggingface.co/datasets/{repo}")


if __name__ == "__main__":
    main()
