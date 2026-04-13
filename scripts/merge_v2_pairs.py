"""T206b (candidate) — Merge all training pair sources into a v2 candidate.

Not a golden promotion. Produces the training input for the first Colab
fine-tune (T302). Golden/ promotion happens in a separate commit AFTER
the trained model beats the v1 baseline on the dev set (per ADR 006 +
phase 3 plan budget guardrails).

Inputs (all deterministic, seed=42):
  golden/vocabulary_pairs.jsonl                         (Hindi/Hinglish synonyms)
  golden/catalog_pairs.jsonl                            (scraped catalog)
  experiments/2026-04-13-kg-pairs/system_pairs.jsonl    (T201b)
  experiments/2026-04-13-kg-pairs/diagnostic_pairs.jsonl(T202b)
  experiments/2026-04-13-kg-pairs/hsn_hierarchy_pairs.jsonl (T200b)

Output:
  experiments/2026-04-13-kg-pairs/all_pairs_v2_candidate.jsonl

Dedup key: (text_a.lower(), text_b.lower()) — canonicalized so (a,b) and
(b,a) collapse. When duplicates exist across sources, the highest label
wins (a 1.0 positive outranks a 0.85 sibling).

Usage:
    python3 -m scripts.merge_v2_pairs
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

GOLDEN = Path("data/training/golden")
EXP = Path("data/training/experiments/2026-04-13-kg-pairs")
OUT = EXP / "all_pairs_v2_candidate.jsonl"

SOURCES = [
    GOLDEN / "vocabulary_pairs.jsonl",
    GOLDEN / "catalog_pairs.jsonl",
    EXP / "system_pairs.jsonl",
    EXP / "diagnostic_pairs.jsonl",
    EXP / "hsn_hierarchy_pairs.jsonl",
]


def _catalog_positive_label(rec: dict) -> float | None:
    """Downgrade catalog positives based on grouping specificity.

    Key format is `group:<cat>|<brand>|<model>` — tighter keys = cleaner
    synonyms. 1-part (brand only) groups are noise (fender == tail panel
    within 'bajaj'); 2-part (brand|model) is related but not same-part;
    3-part (cat|brand|model) is a true synonym.

    Returns: new label, or None to drop the pair entirely.
    """
    src = rec.get("source", "")
    if not src.startswith("group:"):
        return rec.get("label", 1.0)
    parts = src[len("group:"):].split("|")
    n = len(parts)
    if n >= 3:
        return 1.0      # same part category + same vehicle → synonym
    if n == 2:
        return 0.5      # same vehicle, mixed parts → related, not synonym
    return None         # brand-only: drop


def main() -> None:
    best: dict[tuple[str, str], dict] = {}
    per_source: Counter[str] = Counter()
    dropped_catalog = 0
    downgraded_catalog = 0
    for src in SOURCES:
        if not src.exists():
            print(f"MISSING: {src}")
            continue
        n = 0
        with src.open() as f:
            for line in f:
                rec = json.loads(line)
                # Filter catalog_positive by grouping specificity.
                if rec.get("pair_type") == "catalog_positive":
                    new_label = _catalog_positive_label(rec)
                    if new_label is None:
                        dropped_catalog += 1
                        continue
                    if new_label < rec.get("label", 1.0):
                        downgraded_catalog += 1
                        rec = {**rec, "label": new_label}
                a, b = rec["text_a"], rec["text_b"]
                key = tuple(sorted([a.lower(), b.lower()]))
                prior = best.get(key)
                if prior is None or rec.get("label", 1.0) > prior.get("label", 1.0):
                    best[key] = rec
                n += 1
        per_source[src.name] = n
    print(f"catalog_positive: dropped {dropped_catalog} brand-only pairs, "
          f"downgraded {downgraded_catalog} brand+model pairs to 0.5")

    merged = sorted(best.values(), key=lambda r: (r["pair_type"], r["text_a"].lower(), r["text_b"].lower()))

    with OUT.open("w") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    by_type = Counter(r["pair_type"] for r in merged)
    by_label = Counter(f"{r.get('label', 1.0):.2f}" for r in merged)

    print(f"wrote {len(merged)} pairs -> {OUT}")
    print("\nPer source (pre-dedup):")
    for s, n in per_source.most_common():
        print(f"  {s}: {n}")
    print("\nPer pair_type (post-dedup):")
    for t, n in by_type.most_common():
        print(f"  {t}: {n}")
    print("\nLabel distribution:")
    for lbl, n in sorted(by_label.items()):
        print(f"  {lbl}: {n}")


if __name__ == "__main__":
    main()
