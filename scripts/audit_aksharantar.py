"""Audit 1 — Aksharantar precision check.

Sample 100 pairs from the 6,123 auto-relevant Aksharantar transliterations,
ask DeepSeek to classify each as:
  2 = AUTO          (clearly an auto-parts or vehicle term)
  1 = AUTO-ADJACENT (related: tool, system, vehicle generic)
  0 = NOISE         (unrelated: brand spillover, generic English)

Output: data/external/processed/aksharantar_audit.jsonl + precision summary.

Usage:
    python3.11 -m scripts.audit_aksharantar
"""
from __future__ import annotations

import json
import os
import random
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from scripts._env import load_env

load_env()

SRC = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
OUT = Path("data/external/processed/aksharantar_audit.jsonl")
N_SAMPLE = 100
SEED = 42

SYSTEM = """You classify transliteration pairs (Roman <-> Devanagari) for an Indian auto-parts search dataset. For each pair, decide if it is genuine auto-domain content.

Return ONLY a JSON array of integer grades. No prose.
  2 = AUTO: clearly an auto-parts, vehicle, or mechanic's tool term (e.g. silencer, sparkplug, dashboard, transmission, piston, brake)
  1 = AUTO-ADJACENT: a word that could legitimately show up in auto context but is generic (e.g. accelerator, material, monitoring, horizontal, clearance, sensor)
  0 = NOISE: unrelated to auto (e.g. gutkha, community, elements, filament in a general sense, photovoltaic, appliances, heading)

Array length MUST equal input count. Example: [2,1,0,2,1,0,0,2]"""


def judge_batch(pairs: list[dict], api_key: str) -> list[int]:
    numbered = "\n".join(
        f"{i+1}. {p['roman']} <-> {p['devanagari']}" for i, p in enumerate(pairs)
    )
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Classify these {len(pairs)} transliteration pairs:\n{numbered}\n\nReturn the {len(pairs)}-element array."},
        ],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body, timeout=120,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content.split("\n", 1)[1].strip()
            import re
            matches = re.findall(r"\[[\d,\s]+\]", content)
            if matches:
                grades = json.loads(matches[-1])
            else:
                grades = json.loads(content)
            if len(grades) < len(pairs):
                grades = grades + [0] * (len(pairs) - len(grades))
            else:
                grades = grades[: len(pairs)]
            return grades
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    all_pairs = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    print(f"total aksharantar pairs: {len(all_pairs)}")
    rng = random.Random(SEED)
    sample = rng.sample(all_pairs, N_SAMPLE)

    BATCH = 25
    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_grades = []
    with OUT.open("w") as f:
        for i in range(0, len(sample), BATCH):
            chunk = sample[i : i + BATCH]
            print(f"batch {i // BATCH + 1}/{(len(sample) + BATCH - 1)//BATCH} ({len(chunk)} pairs)")
            grades = judge_batch(chunk, key)
            for p, g in zip(chunk, grades):
                rec = {**p, "grade": g}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                all_grades.append(g)

    c = Counter(all_grades)
    total = sum(c.values())
    print("\n=== AKSHARANTAR AUDIT SUMMARY ===")
    print(f"sample size: {total}")
    print(f"  AUTO (2):          {c[2]:3d} ({100*c[2]/total:4.1f}%)")
    print(f"  AUTO-ADJACENT (1): {c[1]:3d} ({100*c[1]/total:4.1f}%)")
    print(f"  NOISE (0):         {c[0]:3d} ({100*c[0]/total:4.1f}%)")
    print(f"\nprecision (AUTO only):         {c[2]/total:.3f}")
    print(f"precision (AUTO + ADJACENT):   {(c[2]+c[1])/total:.3f}")
    print(f"\n-> projected yield at 6,123 pairs:")
    print(f"     AUTO-only:     ~{int(6123*c[2]/total)} clean pairs")
    print(f"     + ADJACENT:    ~{int(6123*(c[2]+c[1])/total)} usable pairs")

    # Show examples of each
    print("\n=== EXAMPLES ===")
    by_grade = {0: [], 1: [], 2: []}
    for line in OUT.read_text().splitlines():
        r = json.loads(line)
        by_grade[r["grade"]].append(r)
    for g, label in [(2, "AUTO"), (1, "ADJACENT"), (0, "NOISE")]:
        print(f"\n{label} (showing 8):")
        for r in by_grade[g][:8]:
            print(f"  {r['roman']:25s} <-> {r['devanagari']}")


if __name__ == "__main__":
    main()
