"""Step 3 — Enrich KG with Hinglish-Devanagari aliases via DeepSeek V3.

For each unique latin KG token (~2,700 parts/aliases/symptoms/systems),
ask DeepSeek to produce the common Devanagari renderings Indian mechanics
actually use. Include BOTH:
  - translation (tel -> तेल)
  - Hinglish transliteration (oil -> ऑयल)

Output format (JSONL):
  {"term": "oil", "renderings": ["ऑयल", "तेल"], "source": "deepseek-v3"}

Merges with Aksharantar-derived bridge to form a unified bridge consumed
by KG-gap analysis and by pair-mining.

Usage:
    python3.11 -m scripts.enrich_kg_hinglish
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import requests

from scripts._env import load_env

load_env()

GRAPH_DB = Path("data/knowledge_graph/graph.db")
OUT = Path("data/external/processed/kg_hinglish_bridge.jsonl")
BATCH = 40
MAX_RENDERINGS = 3
SEED = 42

SYSTEM = """You are an Indian auto-parts mechanic and bilingual editor. For each English term, output up to 3 common Devanagari (Hindi script) renderings Indian mechanics actually say in the workshop.

Include BOTH when both are common:
  1. Translation (the meaning in Hindi), e.g. oil -> तेल
  2. Hinglish transliteration (the English word written in Devanagari), e.g. oil -> ऑयल

Only include terms if the term is a REAL auto-parts / vehicle / mechanic's-tool term. Skip brand names, generic English, and non-auto words — output [] for those.

Return ONLY a JSON object mapping each input term (exactly as given, lowercase) to its array of renderings. No prose, no markdown fences.

Example:
Input: ["oil", "brake", "random_noise"]
Output: {"oil": ["ऑयल", "तेल"], "brake": ["ब्रेक"], "random_noise": []}"""


def load_kg_tokens() -> list[str]:
    """Extract unique latin tokens from KG parts/aliases/symptoms/systems."""
    conn = sqlite3.connect(GRAPH_DB)
    tokens: set[str] = set()
    for (name,) in conn.execute(
        "SELECT name FROM nodes WHERE type IN ('part','alias','symptom','system')"
    ):
        if not name:
            continue
        # Use BOTH: the whole phrase and individual tokens
        # Whole phrase (lowercased) for compound terms like "brake pad"
        phrase = name.strip().lower()
        if re.search(r"[A-Za-z]", phrase) and len(phrase) <= 40:
            tokens.add(phrase)
        # Also single tokens
        for tok in re.split(r"[\s\-/|,]+", phrase):
            tok = tok.strip().lower()
            if re.match(r"^[a-z][a-z0-9]*$", tok) and 3 <= len(tok) <= 20:
                tokens.add(tok)
    conn.close()
    return sorted(tokens)


def batch_translate(terms: list[str], api_key: str) -> dict[str, list[str]]:
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Terms: {json.dumps(terms, ensure_ascii=False)}"},
        ],
        "temperature": 0.0,
        "max_tokens": 3000,
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
            m = re.search(r"\{.*\}", content, re.DOTALL)
            obj = json.loads(m.group(0) if m else content)
            # Sanitize: ensure values are list[str] with Devanagari
            out: dict[str, list[str]] = {}
            for k, v in obj.items():
                if not isinstance(v, list):
                    continue
                clean = []
                for x in v[:MAX_RENDERINGS]:
                    if isinstance(x, str) and re.search(r"[\u0900-\u097F]", x):
                        clean.append(x.strip())
                out[k.lower()] = clean
            return out
        except Exception as e:
            print(f"  attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def main() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    tokens = load_kg_tokens()
    print(f"KG tokens to enrich: {len(tokens)}")

    # Resume support
    OUT.parent.mkdir(parents=True, exist_ok=True)
    done: set[str] = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                done.add(json.loads(line)["term"])
        print(f"resuming — {len(done)} terms already enriched")

    to_do = [t for t in tokens if t not in done]
    print(f"to process: {len(to_do)} terms in {(len(to_do)+BATCH-1)//BATCH} batches")

    with OUT.open("a") as f:
        for i in range(0, len(to_do), BATCH):
            batch = to_do[i : i + BATCH]
            print(f"batch {i//BATCH + 1}/{(len(to_do)+BATCH-1)//BATCH} ({len(batch)} terms)")
            try:
                result = batch_translate(batch, api_key)
            except Exception as e:
                print(f"  BATCH FAILED: {e}", file=sys.stderr)
                continue
            kept = 0
            for term in batch:
                renderings = result.get(term.lower(), [])
                if renderings:
                    f.write(json.dumps({"term": term, "renderings": renderings, "source": "deepseek-v3"}, ensure_ascii=False) + "\n")
                    kept += 1
            f.flush()
            print(f"  kept {kept}/{len(batch)} with renderings")

    # Summary
    n_with = 0
    n_empty = 0
    sample: list[dict] = []
    for line in OUT.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        if r["renderings"]:
            n_with += 1
            if len(sample) < 25:
                sample.append(r)
        else:
            n_empty += 1
    print(f"\n=== DONE ===")
    print(f"terms with renderings: {n_with}")
    print(f"sample ({len(sample)}):")
    for s in sample:
        print(f"  {s['term']:25s} -> {', '.join(s['renderings'])}")


if __name__ == "__main__":
    main()
