"""T201b — Generate ITI system-membership training pairs.

For each `in_system` edge in graph.db, emit pairs that teach the model
which parts belong to which system, and which parts co-occur within a
system. Aliases are expanded so Hindi/Hinglish surface forms also map
correctly.

Pair shape (matches existing vocabulary/catalog format):
    {"text_a": str, "text_b": str, "label": 1.0,
     "pair_type": "system_membership" | "system_cooccurrence",
     "source": "iti_v2"}

Usage:
    python3 -m training.iti_system_pairs
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
OUT = Path("data/training/experiments/2026-04-13-kg-pairs/system_pairs.jsonl")

MAX_COOCCUR_PER_SYSTEM = 80  # cap (k choose 2) explosion for big systems

# Co-occurrence is a RELATED signal, not a SAME-MEANING signal. Two parts
# in the same system (e.g. "brake pad" and "brake disc") are neighbors in
# embedding space but not synonyms — label them graded so MNR-style losses
# filter them out and CoSENT-style losses see them as partial matches.
COOCCURRENCE_LABEL = 0.5
MEMBERSHIP_LABEL = 1.0


def aliases_for(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """part_id -> list of alias names (excluding the canonical part name)."""
    out: dict[str, list[str]] = defaultdict(list)
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias' AND "
        "(SELECT type FROM nodes WHERE id = e.dst) = 'part'"
    ):
        out[part_id].append(alias_name)
    return out


def surface_forms(part_name: str, aliases: list[str]) -> list[str]:
    seen: set[str] = set()
    forms: list[str] = []
    for s in [part_name, *aliases]:
        key = s.strip().lower()
        if key and key not in seen:
            seen.add(key)
            forms.append(s.strip())
    return forms


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB)

    systems = {sid: name for sid, name in conn.execute(
        "SELECT id, name FROM nodes WHERE type='system'"
    )}
    parts = {pid: name for pid, name in conn.execute(
        "SELECT id, name FROM nodes WHERE type='part'"
    )}
    aliases = aliases_for(conn)

    # part_id -> [system_ids]
    members: dict[str, list[str]] = defaultdict(list)
    for part_id, sys_id in conn.execute(
        "SELECT src, dst FROM edges WHERE type='in_system'"
    ):
        if part_id in parts and sys_id in systems:
            members[part_id].append(sys_id)

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

    # (part surface form, system name)
    for part_id, sys_ids in members.items():
        forms = surface_forms(parts[part_id], aliases.get(part_id, []))
        for sys_id in sys_ids:
            sys_name = systems[sys_id]
            for form in forms:
                add(form, sys_name, "system_membership", MEMBERSHIP_LABEL)

    # Co-occurrence: pairs of co-member parts within each system, capped.
    system_to_parts: dict[str, list[str]] = defaultdict(list)
    for part_id, sys_ids in members.items():
        for sys_id in sys_ids:
            system_to_parts[sys_id].append(part_id)

    for sys_id, part_ids in system_to_parts.items():
        if len(part_ids) < 2:
            continue
        all_combos = list(combinations(sorted(part_ids), 2))
        rng.shuffle(all_combos)
        for p1, p2 in all_combos[:MAX_COOCCUR_PER_SYSTEM]:
            # Use canonical names only for co-occurrence to keep signal clean.
            add(parts[p1], parts[p2], "system_cooccurrence", COOCCURRENCE_LABEL)

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
