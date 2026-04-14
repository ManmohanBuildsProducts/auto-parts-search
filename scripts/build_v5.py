"""Build v5 training set.

v5 = v3 positives (7,828) + filtered Aksharantar (3,660) + query-ified YT pairs
     (subset of 376 that produced real user-query rewrites).

Drops: Hinglish bridge (harmful per v4c), raw YT chunks (harmful per v4a).

Output: data/external/processed/v4_variants/v5.jsonl

Usage:
    python3.11 -m scripts.build_v5
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

GOLDEN_V2 = Path("data/training/golden/all_pairs_v2.jsonl")
AKS = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
YT_Q = Path("data/external/processed/yt_pairs_v5_queryified.jsonl")
OUT = Path("data/external/processed/v4_variants/v5.jsonl")

AKS_NOISE_STOPLIST = {
    "heading", "gutkha", "elements", "photovoltaic", "filament", "tandem",
    "sheesha", "reg", "inline", "race", "separator", "push", "roll",
    "centrifugal", "community", "horizontal", "monitoring", "maintenance",
    "accessories", "clearance", "resistance", "combination", "constant",
    "stability", "prevention", "interior", "exterior", "material",
    "components", "devices", "points", "transformers", "distribution",
    "engagement", "appliances",
}


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pairs: list[dict] = []

    # 1. v3 positives
    for line in GOLDEN_V2.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        if r.get("label", 1.0) >= 1.0:
            pairs.append(r)
    n_v3 = len(pairs)
    print(f"v3 positives: {n_v3}")

    # 2. Aksharantar filtered
    for line in AKS.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        if r["roman"].strip().lower() in AKS_NOISE_STOPLIST:
            continue
        pairs.append({
            "text_a": r["roman"].strip().lower(),
            "text_b": r["devanagari"].strip(),
            "label": 1.0,
            "pair_type": "aksharantar_synonym",
            "source": "ai4bharat_aksharantar",
        })
    n_aks = len(pairs) - n_v3
    print(f"+ aksharantar: {n_aks}")

    # 3. Query-ified YT
    n_yt = 0
    for line in YT_Q.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        if not r.get("text_a") or r.get("label", 0) < 1.0:
            continue
        pairs.append({
            "text_a": r["text_a"],
            "text_b": r["text_b"],
            "label": 1.0,
            "pair_type": "yt_queryified",
            "source": r.get("source", "yt_pilot"),
        })
        n_yt += 1
    print(f"+ queryified yt: {n_yt}")

    # Dedup
    seen: set[tuple[str, str]] = set()
    final: list[dict] = []
    for p in pairs:
        k = (p["text_a"].strip().lower(), p["text_b"].strip().lower())
        if k in seen:
            continue
        seen.add(k)
        final.append(p)

    with OUT.open("w") as f:
        for p in final:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    c = Counter(p["pair_type"] for p in final)
    print(f"\nv5 total: {len(final)} pairs")
    for t, n in c.most_common():
        print(f"  {t}: {n}")


if __name__ == "__main__":
    main()
