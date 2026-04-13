"""Fetch AI4Bharat public datasets, filter for auto-parts relevance.

Two datasets pulled via HuggingFace Datasets:

1. **Aksharantar (Hindi)** — 26M Hindi↔Roman transliteration pairs.
   We extract pairs where either side contains any of our KG auto aliases
   (top-500 common tokens). Builds a direct Roman↔Devanagari bridge
   (e.g. patti↔पट्टी, silencer↔साइलेंसर).

2. **IndicVoices (Hindi subset)** — transcribed Hindi spontaneous speech.
   We filter transcripts that contain any KG auto token → yields natural
   speech examples containing real auto vocabulary.

Output:
  data/external/processed/ai4bharat_aksharantar_auto.jsonl
  data/external/processed/ai4bharat_indicvoices_auto.jsonl

Usage:
    python3.11 -m scripts.fetch_ai4bharat
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path

OUT_AK = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
OUT_IV = Path("data/external/processed/ai4bharat_indicvoices_auto.jsonl")
GRAPH_DB = Path("data/knowledge_graph/graph.db")


def load_auto_vocab() -> tuple[set[str], set[str]]:
    """Return (latin_terms_lower, devanagari_terms) from the KG."""
    conn = sqlite3.connect(GRAPH_DB)
    latin, devan = set(), set()
    for (name,) in conn.execute(
        "SELECT name FROM nodes WHERE type IN ('part','alias','symptom','system')"
    ):
        if not name:
            continue
        if re.search(r"[\u0900-\u097F]", name):
            devan.add(name.strip())
        if re.search(r"[A-Za-z]", name):
            latin.add(name.strip().lower())
    conn.close()
    # also pull explicit known alias strings via known_as
    return latin, devan


def filter_aksharantar(latin: set[str], devan: set[str]) -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        print("pip install datasets", file=sys.stderr)
        raise

    print("streaming Aksharantar Hindi (trying several HF paths)...")
    # Try in order of likelihood based on AI4Bharat's current repo structure
    attempts = [
        ("ai4bharat/Aksharantar", None),
        ("ai4bharat/Aksharantar", "default"),
        ("ai4bharat/IndicTransliterate", None),
        ("ai4bharat/Dakshina", "hi"),
    ]
    ds = None
    last_err = None
    for name, cfg in attempts:
        try:
            if cfg:
                ds = load_dataset(name, cfg, split="train", streaming=True)
            else:
                ds = load_dataset(name, split="train", streaming=True)
            print(f"  loaded {name} / {cfg}")
            break
        except Exception as e:
            last_err = e
            print(f"  {name} / {cfg}: {type(e).__name__}: {str(e)[:120]}")
    if ds is None:
        print(f"  all aksharantar variants failed; last: {last_err}")
        return 0

    OUT_AK.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    seen = 0
    seen_hi = 0

    # Expand vocab: split multi-word aliases into single tokens too
    single_latin = set()
    for term in latin:
        for tok in re.split(r"[\s\-/]+", term):
            tok = tok.strip().lower()
            if len(tok) >= 3:  # drop "ac", "ag" noise
                single_latin.add(tok)
    print(f"  expanded latin vocab: {len(latin)} phrases -> {len(single_latin)} unique tokens")

    # Devanagari character regex for Hindi filter (Aksharantar is pan-Indic)
    devan_re = re.compile(r"[\u0900-\u097F]")

    with OUT_AK.open("w") as f:
        for rec in ds:
            seen += 1
            eng = (rec.get("english word") or rec.get("english_word") or "").strip().lower()
            nat = (rec.get("native word") or rec.get("native_word") or "").strip()
            if not eng or not nat:
                continue
            # Hindi filter: native text must contain Devanagari
            if not devan_re.search(nat):
                continue
            seen_hi += 1
            # Match: either whole eng token matches a single-word auto vocab, or any word in eng matches
            eng_tokens = re.split(r"[\s\-]+", eng)
            if eng in single_latin or any(t in single_latin for t in eng_tokens):
                f.write(json.dumps({"roman": eng, "devanagari": nat, "id": rec.get("unique_identifier")}, ensure_ascii=False) + "\n")
                n += 1
            if seen >= 30_000_000:  # hard cap
                break
    print(f"aksharantar: scanned {seen:,} total, {seen_hi:,} Hindi, kept {n} auto-relevant -> {OUT_AK}")
    return n


def filter_indicvoices(latin: set[str], devan: set[str]) -> int:
    try:
        from datasets import load_dataset
    except ImportError:
        return 0

    print("streaming IndicVoices Hindi (ai4bharat/IndicVoices)...")
    try:
        ds = load_dataset("ai4bharat/IndicVoices", "hindi", split="train", streaming=True)
    except Exception as e:
        print(f"  failed to load IndicVoices hindi: {e}")
        # Try alternative — IndicVoices_v2 or IndicVoices-R
        try:
            ds = load_dataset("ai4bharat/IndicVoices-R", "hindi", split="train", streaming=True)
            print("  loaded IndicVoices-R")
        except Exception as e2:
            print(f"  IndicVoices-R also failed: {e2}")
            return 0

    OUT_IV.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    seen = 0
    # Pre-compile regex of all terms
    terms = sorted(latin | {d for d in devan if len(d) >= 3}, key=len, reverse=True)
    pattern = re.compile("|".join(re.escape(t) for t in terms[:2000]), re.I)

    with OUT_IV.open("w") as f:
        for rec in ds:
            seen += 1
            transcript = (rec.get("transcript") or rec.get("text") or rec.get("sentence") or "").strip()
            if not transcript:
                continue
            m = pattern.search(transcript)
            if m:
                f.write(json.dumps({
                    "transcript": transcript,
                    "match": m.group(0),
                    "language": rec.get("language", "hi"),
                    "speaker_id": rec.get("speaker_id"),
                }, ensure_ascii=False) + "\n")
                n += 1
            if seen >= 50_000:
                break
    print(f"indicvoices: scanned {seen:,}, kept {n} auto-mentioning transcripts -> {OUT_IV}")
    return n


def main() -> None:
    latin, devan = load_auto_vocab()
    print(f"KG auto vocab: {len(latin)} latin, {len(devan)} devanagari terms")

    n_ak = filter_aksharantar(latin, devan)
    n_iv = filter_indicvoices(latin, devan)
    print(f"\ntotal auto-relevant: aksharantar={n_ak}, indicvoices={n_iv}")


if __name__ == "__main__":
    main()
