"""Step 4 — Pair-mine YouTube transcripts into v4 training pairs.

For each clean YouTube transcript chunk, ask DeepSeek to identify the
auto-parts / symptoms / systems mentioned in English canonical form.
Then match those mentions back to our KG (via latin name or Hinglish
bridge). Emit (chunk_text, kg_part_name) pairs with label=1.0.

Quality gates:
  - drop chunks with zero KG matches (no signal)
  - drop chunks < 80 chars (likely ASR noise)
  - exclude polluted channel (UC_ac2x2rwzSwCDMwvcFooOA)

Output: data/external/processed/yt_pairs_v4.jsonl

Usage:
    python3.11 -m scripts.mine_yt_pairs
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import requests

from scripts._env import load_env

load_env()

YT_DIR = Path("data/external/yt_pilot")
HINGLISH = Path("data/external/processed/kg_hinglish_bridge.jsonl")
AKS = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
GRAPH_DB = Path("data/knowledge_graph/graph.db")
OUT = Path("data/external/processed/yt_pairs_v4.jsonl")

EXCLUDE_CHANNELS = {"UC_ac2x2rwzSwCDMwvcFooOA"}  # My Mechanical Support (off-topic pollution)
CHUNK_CHARS = 400
CHUNK_OVERLAP = 60
MIN_CHUNK_CHARS = 80
DEVAN_RE = re.compile(r"[\u0900-\u097F]")

EXTRACT_SYSTEM = """You are an Indian auto-parts mechanic reading a short snippet of a mechanic's Hindi/Hinglish speech. Extract the names of every AUTO-PART, SYSTEM, or SYMPTOM mentioned in the snippet.

Return ONLY a JSON array of English canonical strings. Each string should be a concrete part / system / symptom, NOT a verb or generic word.
  Good: ["brake pad", "timing chain", "engine", "spark plug", "engine overheating"]
  Bad: ["repair", "problem", "maintenance", "work", "check"] (too generic)

Return [] if no auto-parts are mentioned. No prose, no markdown, just the JSON array."""


def load_kg() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Return (latin_phrase -> canonical_part_name, devanagari_token -> [canonical_part_names])."""
    conn = sqlite3.connect(GRAPH_DB)
    latin_to_part: dict[str, str] = {}  # lowercased phrase -> canonical name
    aliases_by_part: dict[str, list[str]] = defaultdict(list)
    # Pull alias->part via known_as
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias'"
    ):
        aliases_by_part[part_id].append(alias_name)
    # Canonical part names
    part_names: dict[str, str] = {}
    for pid, name in conn.execute("SELECT id, name FROM nodes WHERE type='part'"):
        part_names[pid] = name
        latin_to_part[name.strip().lower()] = name
        for tok in re.split(r"[\s\-/|,:]+", name.strip().lower()):
            if len(tok) >= 4 and re.match(r"^[a-z]", tok):
                latin_to_part.setdefault(tok, name)
    # Also map all aliases back to canonical
    for pid, als in aliases_by_part.items():
        canon = part_names.get(pid, pid)
        for a in als:
            a_low = a.strip().lower()
            if re.search(r"[a-z]", a_low):
                latin_to_part.setdefault(a_low, canon)
    # Symptoms + systems as possible matches too
    for (name,) in conn.execute("SELECT name FROM nodes WHERE type IN ('symptom', 'system')"):
        if name:
            latin_to_part.setdefault(name.strip().lower(), name.strip())
    conn.close()
    return latin_to_part, aliases_by_part


def load_devanagari_to_part() -> dict[str, str]:
    """Build Devanagari -> canonical-latin-part-name from our enriched bridge."""
    dev_to_latin: dict[str, str] = {}
    if HINGLISH.exists():
        for line in HINGLISH.read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line)
            term = r["term"]  # latin KG token (lower)
            for rend in r["renderings"]:
                dev_to_latin.setdefault(rend.strip(), term)
    # Also Aksharantar
    if AKS.exists():
        for line in AKS.read_text().splitlines():
            if not line.strip(): continue
            r = json.loads(line)
            dev_to_latin.setdefault(r["devanagari"].strip(), r["roman"].strip().lower())
    return dev_to_latin


def chunks(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = text.strip()
    if len(text) <= size:
        return [text] if len(text) >= MIN_CHUNK_CHARS else []
    # Try to break at sentence-ish boundaries
    out = []
    i = 0
    while i < len(text):
        window = text[i : i + size]
        # Extend to next purna-viram or newline within next 80 chars
        if i + size < len(text):
            tail = text[i + size : i + size + 80]
            m = re.search(r"[।\.\n]", tail)
            if m:
                window += tail[: m.end()]
        if len(window.strip()) >= MIN_CHUNK_CHARS:
            out.append(window.strip())
        i += size - overlap
    return out


def extract_mentions(chunk: str, api_key: str) -> list[str]:
    body = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": EXTRACT_SYSTEM},
            {"role": "user", "content": chunk},
        ],
        "temperature": 0.0,
        "max_tokens": 400,
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
            m = re.search(r"\[.*\]", content, re.DOTALL)
            arr = json.loads(m.group(0) if m else content)
            return [str(x).strip().lower() for x in arr if isinstance(x, str) and x.strip()]
        except Exception as e:
            if attempt == 2:
                print(f"  extract failed: {e}", file=sys.stderr)
                return []
            time.sleep(2 ** attempt)
    return []


def match_mention(mention: str, latin_to_part: dict[str, str]) -> str | None:
    """Map a mention string to a canonical KG part name, or None."""
    m = mention.strip().lower()
    if m in latin_to_part:
        return latin_to_part[m]
    # Try each whitespace-separated segment
    for tok in re.split(r"[\s\-/]+", m):
        if tok in latin_to_part:
            return latin_to_part[tok]
    # Try substring contains from the other direction
    for key, canon in latin_to_part.items():
        if len(key) >= 4 and key in m:
            return canon
    return None


def main() -> None:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print("ERROR: DEEPSEEK_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    latin_to_part, _ = load_kg()
    print(f"KG lookup: {len(latin_to_part)} latin keys")

    # Resume
    done_chunks: set[str] = set()
    if OUT.exists():
        for line in OUT.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                done_chunks.add(r.get("_chunk_key", ""))
        print(f"resuming — {len(done_chunks)} chunks already mined")

    total_chunks = 0
    kept_pairs = 0
    skipped_no_match = 0
    per_video: list[dict] = []

    with OUT.open("a") as f:
        for fp in sorted(YT_DIR.rglob("*.json")):
            # Skip polluted channels
            if fp.parent.name in EXCLUDE_CHANNELS:
                continue
            j = json.loads(fp.read_text())
            text = j.get("full_transcript", "")
            vid_id = j.get("video_meta", {}).get("id") or fp.stem
            if not text:
                continue
            ch = chunks(text)
            print(f"\n{fp.parent.name}/{vid_id}: {len(text)} chars, {len(ch)} chunks")
            v_kept = 0; v_skipped = 0
            for ci, chunk in enumerate(ch):
                key = f"{fp.parent.name}/{vid_id}:{ci}"
                if key in done_chunks:
                    continue
                total_chunks += 1
                mentions = extract_mentions(chunk, api_key)
                matched: list[str] = []
                seen_canon: set[str] = set()
                for m in mentions:
                    canon = match_mention(m, latin_to_part)
                    if canon and canon not in seen_canon:
                        seen_canon.add(canon)
                        matched.append(canon)
                if not matched:
                    skipped_no_match += 1
                    v_skipped += 1
                    continue
                for canon in matched:
                    rec = {
                        "_chunk_key": key,
                        "text_a": chunk,
                        "text_b": canon,
                        "label": 1.0,
                        "pair_type": "yt_mechanic_speech",
                        "source": f"yt:{fp.parent.name}/{vid_id}",
                        "extracted_mentions": mentions,
                    }
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    kept_pairs += 1
                    v_kept += 1
                f.flush()
            per_video.append({"video": f"{fp.parent.name}/{vid_id}", "chunks": len(ch), "pairs": v_kept, "skipped": v_skipped})
            print(f"  pairs kept: {v_kept} | skipped no-match: {v_skipped}")

    print(f"\n=== YT PAIR MINING SUMMARY ===")
    print(f"total chunks processed:  {total_chunks}")
    print(f"chunks skipped (no match): {skipped_no_match}")
    print(f"pairs written:           {kept_pairs}")
    print(f"\nper-video:")
    for v in per_video:
        print(f"  {v['video']}: {v['chunks']} chunks -> {v['pairs']} pairs (skipped {v['skipped']})")


if __name__ == "__main__":
    main()
