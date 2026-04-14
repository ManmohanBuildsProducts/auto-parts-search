"""Transform YT mechanic-monologue chunks into user-query-style pairs.

For each (chunk_text, canonical_part_name) pair in yt_pairs_v4_clean.jsonl,
ask DeepSeek to rewrite the chunk as a realistic Hindi/Hinglish user query
that would retrieve that part. Replace text_a with the query; keep text_b
as the canonical KG part name; label = 1.0.

Drop the pair if the LLM returns empty, a refusal, or the rewrite doesn't
mention the part.

Output: data/external/processed/yt_pairs_v5_queryified.jsonl

Usage:
    python3.11 -m scripts.queryify_yt_pairs
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

from scripts._env import load_env

load_env()

SRC = Path("data/external/processed/yt_pairs_v4_clean.jsonl")
OUT = Path("data/external/processed/yt_pairs_v5_queryified.jsonl")

SYSTEM = """You rewrite a mechanic's Hindi/Hinglish monologue snippet as a realistic USER QUERY — the kind a vehicle owner would type into an auto-parts search box on a phone.

Input: a Hindi/Hinglish snippet + the canonical English auto-part the snippet discusses.
Output: a single Hindi/Hinglish user query (1-12 words), in the voice of a real owner / non-expert user. Code-mix natural. Include the part by name OR a common colloquial reference (e.g. patti for brake pad, shocker for shock absorber, silencer for muffler).

Return ONLY a JSON object: {"query": "..."} — no prose, no markdown, no reasoning.

Examples of good queries:
  {"query": "mere bike ka spark plug badalna hai kitne ka aata hai"}
  {"query": "wagon r ka o2 sensor kaun sa lagega"}
  {"query": "activa ke liye engine oil best konsa hai"}
  {"query": "brake patti change karni hai swift ki"}

If the part isn't really discussed OR it's too generic to query, return {"query": ""}."""


def queryify(chunk: str, part_name: str, api_key: str) -> str | None:
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Canonical part: {part_name}\nSnippet: {chunk}"},
        ],
        "temperature": 0.3,
        "max_tokens": 120,
    }
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body, timeout=60,
            )
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                if content.startswith("json"):
                    content = content.split("\n", 1)[1].strip()
            m = re.search(r"\{.*\}", content, re.DOTALL)
            if not m:
                return None
            obj = json.loads(m.group(0))
            q = (obj.get("query") or "").strip()
            if not q or len(q) < 4 or len(q) > 200:
                return None
            return q
        except Exception as e:
            if attempt == 2:
                print(f"  queryify failed: {e}", file=sys.stderr)
                return None
            time.sleep(2 ** attempt)
    return None


def main() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # Resume
    done_keys: set[str] = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done_keys.add(r.get("_src_key", ""))
        print(f"resuming — {len(done_keys)} already done")

    src_pairs = [json.loads(l) for l in SRC.read_text().splitlines() if l.strip()]
    print(f"source pairs: {len(src_pairs)}")

    kept = 0; dropped = 0
    with OUT.open("a") as f:
        for i, p in enumerate(src_pairs, 1):
            key = p.get("_chunk_key", "") + "||" + p["text_b"]
            if key in done_keys:
                continue
            q = queryify(p["text_a"], p["text_b"], api_key)
            if not q:
                dropped += 1
                # Still write a placeholder with empty query so we don't retry
                f.write(json.dumps({"_src_key": key, "text_a": "", "text_b": p["text_b"], "label": 0.0, "pair_type": "yt_queryified_empty", "source": p.get("source", "yt_pilot")}, ensure_ascii=False) + "\n")
                f.flush()
                continue
            rec = {
                "_src_key": key,
                "text_a": q,
                "text_b": p["text_b"],
                "label": 1.0,
                "pair_type": "yt_queryified",
                "source": p.get("source", "yt_pilot"),
                "_orig_chunk": p["text_a"][:200],
            }
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            kept += 1
            if i % 20 == 0:
                print(f"  [{i}/{len(src_pairs)}] kept={kept} dropped={dropped}")

    # Summary
    all_out = [json.loads(l) for l in OUT.read_text().splitlines()]
    non_empty = [r for r in all_out if r.get("text_a")]
    print(f"\ntotal records: {len(all_out)}  non-empty queries: {len(non_empty)}  empty/dropped: {len(all_out)-len(non_empty)}")
    print("\n10 random queries:")
    import random
    random.seed(42)
    for r in random.sample(non_empty, min(10, len(non_empty))):
        print(f"  {r['text_b']:30s} <- {r['text_a']}")


if __name__ == "__main__":
    main()
