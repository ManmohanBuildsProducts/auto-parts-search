"""T200b — Generate HSN-hierarchy graded training pairs.

Uses the HSN taxonomy in graph.db (category parent_of category, part is_a
category) to produce graded-relevance pairs:

  - sibling pairs (same parent category) -> label 0.85
  - cousin pairs  (parent categories share a grandparent) -> label 0.40

These graded labels (vs. hard 1.0) give the model a soft signal that
"piston ring" and "cylinder head" are related but not identical, and
"piston ring" and "brake pad" are in different neighborhoods entirely.

Pair shape:
    {"text_a": str, "text_b": str, "label": float,
     "pair_type": "hsn_sibling" | "hsn_cousin",
     "source": "hsn_cbic"}

Usage:
    python3 -m training.hsn_hierarchy_pairs
"""
from __future__ import annotations

import json
import random
import sqlite3
from collections import defaultdict
from itertools import combinations, product
from pathlib import Path

from auto_parts_search.config import RANDOM_SEED

DB = Path("data/knowledge_graph/graph.db")
OUT = Path("data/training/experiments/2026-04-13-kg-pairs/hsn_hierarchy_pairs.jsonl")

SIBLING_LABEL = 0.85
COUSIN_LABEL = 0.40
MAX_SIBLINGS_PER_CATEGORY = 60
MAX_COUSINS_PER_GRANDPARENT = 80


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)

    parts = {pid: name for pid, name in conn.execute(
        "SELECT id, name FROM nodes WHERE type='part'"
    )}

    # part -> category (leaf) via is_a
    part_to_cat: dict[str, str] = {}
    for src, dst in conn.execute(
        "SELECT src, dst FROM edges WHERE type='is_a'"
    ):
        if src in parts:
            part_to_cat[src] = dst

    # cat -> parent cat via parent_of (reverse direction)
    parent_of: dict[str, str] = {}
    for src, dst in conn.execute(
        "SELECT src, dst FROM edges WHERE type='parent_of'"
    ):
        parent_of[dst] = src  # src is parent, dst is child

    conn.close()

    # cat -> [part_ids] at that leaf
    cat_to_parts: dict[str, list[str]] = defaultdict(list)
    for pid, cat in part_to_cat.items():
        cat_to_parts[cat].append(pid)

    rng = random.Random(RANDOM_SEED)
    pairs: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(a: str, b: str, label: float, ptype: str) -> None:
        if a.lower() == b.lower():
            return
        # canonicalize direction to avoid duplicate mirrored pairs
        k = tuple(sorted([a.lower(), b.lower()]))
        key = (k[0], k[1], ptype)
        if key in seen:
            return
        seen.add(key)
        pairs.append({
            "text_a": a, "text_b": b, "label": label,
            "pair_type": ptype, "source": "hsn_cbic",
        })

    # Siblings: parts sharing the same parent category
    for cat, pids in cat_to_parts.items():
        if len(pids) < 2:
            continue
        combos = list(combinations(sorted(set(pids)), 2))
        rng.shuffle(combos)
        for p1, p2 in combos[:MAX_SIBLINGS_PER_CATEGORY]:
            add(parts[p1], parts[p2], SIBLING_LABEL, "hsn_sibling")

    # Cousins: grandparent -> children categories -> parts across children
    children_of: dict[str, list[str]] = defaultdict(list)
    for child, parent in parent_of.items():
        children_of[parent].append(child)

    for gp, child_cats in children_of.items():
        # Collect parts under each child cat (direct only; deeper trees skipped)
        child_buckets = [
            (c, cat_to_parts.get(c, [])) for c in child_cats
        ]
        child_buckets = [b for b in child_buckets if b[1]]
        if len(child_buckets) < 2:
            continue
        cross_pairs: list[tuple[str, str]] = []
        for (c1, p1_list), (c2, p2_list) in combinations(child_buckets, 2):
            for p1, p2 in product(p1_list, p2_list):
                cross_pairs.append((p1, p2))
        rng.shuffle(cross_pairs)
        for p1, p2 in cross_pairs[:MAX_COUSINS_PER_GRANDPARENT]:
            add(parts[p1], parts[p2], COUSIN_LABEL, "hsn_cousin")

    pairs.sort(key=lambda d: (d["pair_type"], d["text_a"].lower(), d["text_b"].lower()))

    with OUT.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    by_type: dict[str, int] = defaultdict(int)
    for p in pairs:
        by_type[p["pair_type"]] += 1
    print(f"wrote {len(pairs)} pairs -> {OUT}")
    for t, n in sorted(by_type.items()):
        print(f"  {t}: {n}")
    print(f"seed: {RANDOM_SEED}")


if __name__ == "__main__":
    main()
