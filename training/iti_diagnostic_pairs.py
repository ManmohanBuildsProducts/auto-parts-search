"""T202b — Generate ITI diagnostic-chain training pairs.

For each `caused_by` edge (symptom -> part) in graph.db, emit pairs that
teach the model which parts are associated with which symptom complaints.
Aliases are expanded so the model generalizes across surface forms.

Pair shape:
    {"text_a": str, "text_b": str, "label": 1.0,
     "pair_type": "symptom_part" | "symptom_cooccurrence",
     "source": "iti_v2"}

Usage:
    python3 -m training.iti_diagnostic_pairs
"""
from __future__ import annotations

import json
import random
import sqlite3
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from auto_parts_search.config import RANDOM_SEED

DB = Path("data/knowledge_graph/graph.db")
OUT = Path("data/training/experiments/2026-04-13-kg-pairs/diagnostic_pairs.jsonl")

MAX_COOCCUR_PER_SYMPTOM = 40

# Co-occurrence = parts sharing a root cause. Related, not synonymous.
# Graded label so MNR-style positive-only losses drop them; graded losses
# (CoSENT) still see partial signal.
COOCCURRENCE_LABEL = 0.5
SYMPTOM_PART_LABEL = 1.0


def pretty_symptom(raw: str) -> str:
    """symptom:abnormal_engine_noise -> abnormal engine noise."""
    s = raw.split(":", 1)[-1] if raw.startswith("symptom:") else raw
    return s.replace("_", " ").strip()


def aliases_for(conn: sqlite3.Connection) -> dict[str, list[str]]:
    out: dict[str, list[str]] = defaultdict(list)
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias' AND "
        "(SELECT type FROM nodes WHERE id = e.dst) = 'part'"
    ):
        out[part_id].append(alias_name)
    return out


def surface_forms(name: str, aliases: list[str]) -> list[str]:
    seen: set[str] = set()
    forms: list[str] = []
    for s in [name, *aliases]:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            forms.append(s.strip())
    return forms


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)

    symptoms = {sid: pretty_symptom(name) for sid, name in conn.execute(
        "SELECT id, name FROM nodes WHERE type='symptom'"
    )}
    parts = {pid: name for pid, name in conn.execute(
        "SELECT id, name FROM nodes WHERE type='part'"
    )}
    aliases = aliases_for(conn)

    # symptom -> [parts]
    chains: dict[str, list[str]] = defaultdict(list)
    for sym_id, part_id in conn.execute(
        "SELECT src, dst FROM edges WHERE type='caused_by'"
    ):
        if sym_id in symptoms and part_id in parts:
            chains[sym_id].append(part_id)

    conn.close()

    rng = random.Random(RANDOM_SEED)
    pairs: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    def add(a: str, b: str, ptype: str, label: float) -> None:
        key = (a.lower(), b.lower(), ptype)
        if key in seen or a.lower() == b.lower():
            return
        seen.add(key)
        pairs.append({
            "text_a": a, "text_b": b, "label": label,
            "pair_type": ptype, "source": "iti_v2",
        })

    # (symptom text, part surface form)
    for sym_id, part_ids in chains.items():
        sym_name = symptoms[sym_id]
        for part_id in part_ids:
            forms = surface_forms(parts[part_id], aliases.get(part_id, []))
            for form in forms:
                add(sym_name, form, "symptom_part", SYMPTOM_PART_LABEL)

    # Symptom co-occurrence: parts that share a root cause cluster together.
    for sym_id, part_ids in chains.items():
        if len(part_ids) < 2:
            continue
        combos = list(combinations(sorted(set(part_ids)), 2))
        rng.shuffle(combos)
        for p1, p2 in combos[:MAX_COOCCUR_PER_SYMPTOM]:
            add(parts[p1], parts[p2], "symptom_cooccurrence", COOCCURRENCE_LABEL)

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
