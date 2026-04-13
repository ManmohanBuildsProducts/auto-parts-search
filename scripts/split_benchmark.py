"""T208 — Deterministic dev/test split of the 195-query benchmark.

Stratified by query_type to preserve the 6-category balance. Test set is
sealed — only touched for final model release reporting. All iteration
during Phase 3 happens on dev.

Split: ~77% dev / ~23% test (target ~150 / ~45).
Stratification: 8 test queries per type where available (caps at 7 for
part_number/misspelled/brand_as_generic which have 30 each) — gives 46
test queries.

Usage:
    python3 -m scripts.split_benchmark
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

from auto_parts_search.config import RANDOM_SEED

SRC = Path("data/training/golden/benchmark.json")
DEV = Path("data/training/golden/benchmark_dev.json")
TEST = Path("data/training/golden/benchmark_test.json")

# Test set size per query_type. Sums to 46 test queries.
TEST_PER_TYPE = {
    "exact_english": 8,
    "hindi_hinglish": 8,
    "symptom": 8,
    "misspelled": 7,
    "part_number": 7,
    "brand_as_generic": 8,
}


def main() -> None:
    benchmark = json.loads(SRC.read_text())
    by_type: dict[str, list[dict]] = defaultdict(list)
    for q in benchmark:
        by_type[q["query_type"]].append(q)

    rng = random.Random(RANDOM_SEED)
    dev: list[dict] = []
    test: list[dict] = []
    for qtype, queries in by_type.items():
        shuffled = queries.copy()
        rng.shuffle(shuffled)
        n_test = TEST_PER_TYPE.get(qtype, max(1, len(shuffled) // 5))
        test.extend(shuffled[:n_test])
        dev.extend(shuffled[n_test:])

    dev.sort(key=lambda q: (q["query_type"], q["query"]))
    test.sort(key=lambda q: (q["query_type"], q["query"]))

    DEV.write_text(json.dumps(dev, indent=2, ensure_ascii=False))
    TEST.write_text(json.dumps(test, indent=2, ensure_ascii=False))

    print(f"source: {len(benchmark)} queries")
    print(f"dev:    {len(dev)} queries -> {DEV}")
    print(f"test:   {len(test)} queries -> {TEST}  [SEALED]")
    print(f"seed:   {RANDOM_SEED}")

    for split_name, split in [("dev", dev), ("test", test)]:
        counts = defaultdict(int)
        for q in split:
            counts[q["query_type"]] += 1
        print(f"{split_name}: " + ", ".join(f"{t}={n}" for t, n in sorted(counts.items())))


if __name__ == "__main__":
    main()
