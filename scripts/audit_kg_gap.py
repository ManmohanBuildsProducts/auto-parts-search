"""Audit 4 — KG vocabulary gap analysis from YouTube transcripts.

Extract all Devanagari tokens from our YouTube transcripts, intersect with
our KG vocab (expanded via the Aksharantar Roman<->Devanagari bridge), and
report top novel tokens (= things our KG doesn't cover).

Output: data/external/processed/kg_gap_audit.json
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter
from pathlib import Path

GRAPH_DB = Path("data/knowledge_graph/graph.db")
YT_DIR = Path("data/external/yt_pilot")
AKS = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
OUT = Path("data/external/processed/kg_gap_audit.json")

# Devanagari word-boundary token (avoid multi-word blobs)
DEVAN_TOKEN = re.compile(r"[\u0900-\u097F]+")
HINDI_STOP = {
    # core function words
    "है","हैं","का","की","के","को","में","से","पर","और","या","यह","वह",
    "जो","ये","वे","भी","तो","ही","कि","इस","उस","हो","हम","आप","मैं",
    "ने","थी","था","थे","होगा","होगी","हुआ","हुई","एक","दो","अब","जब",
    "कर","करो","करें","लगा","लगे","देख","लो","रख","दिया","दे","मेरी","मेरा",
    "अपनी","अपना","सब","कुछ","सा","सी","से","वही","यहीं","वहां","यहां","देखो",
    "रहा","रही","रहे","जा","आ","आई","रख","चाहिए","पहले","फिर","बाद","साथ",
    "तक","पास","अंदर","बाहर","ऊपर","नीचे","ठीक","अच्छा","सही","बहुत","जाए",
    "जाएगा","जाएगी","होता","होती","होते","नहीं","ना","अगर","तब","हम","उन्हें",
    "उन्हों","मुझे","तुम","कोई","कौन","क्या","कहां","कैसे","क्यों","वाला","वाली",
    "बात","आज","कल","चलो","ले","गया","गई","गए","लिया","लीजिए","दीजिए","दिए",
    "हूं","हूँ","मैंने","तूने","उसने","इन्हीं","जैसे","ऐसा","ऐसी","वैसे","इसे",
    "उसे","लिए","के","लिये","होने","करने","इसी","उसी","यही","आप","देखिए",
    "बोलिए","सुनिए","लीजिये","खुद","कभी","हमेशा","दूसरा","दूसरी","हर","सभी",
    # English borrowings common in mechanic speech (still auto-valid) — NOT stopped
}


def load_kg_latin_vocab() -> set[str]:
    conn = sqlite3.connect(GRAPH_DB)
    vocab = set()
    for (name,) in conn.execute(
        "SELECT name FROM nodes WHERE type IN ('part','alias','symptom','system')"
    ):
        if name:
            for tok in re.split(r"[\s\-/]+", name.lower()):
                tok = tok.strip().lower()
                if len(tok) >= 3:
                    vocab.add(tok)
    conn.close()
    return vocab


def load_aksharantar_bridge() -> dict[str, set[str]]:
    """Return {devanagari_token: {roman_token, ...}} and reverse."""
    devan_to_roman: dict[str, set[str]] = {}
    for line in AKS.read_text().splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        dev = r["devanagari"].strip()
        rom = r["roman"].strip().lower()
        devan_to_roman.setdefault(dev, set()).add(rom)
    return devan_to_roman


def extract_devan_tokens(dir: Path) -> Counter:
    counts: Counter = Counter()
    for fp in dir.rglob("*.json"):
        try:
            j = json.loads(fp.read_text())
        except json.JSONDecodeError:
            continue
        text = j.get("full_transcript", "")
        if not text:
            continue
        for m in DEVAN_TOKEN.finditer(text):
            tok = m.group(0).strip()
            if len(tok) < 2 or tok in HINDI_STOP:
                continue
            counts[tok] += 1
    return counts


def main() -> None:
    print("loading KG vocab...")
    kg = load_kg_latin_vocab()
    print(f"  KG latin tokens: {len(kg)}")

    print("loading Aksharantar bridge...")
    bridge = load_aksharantar_bridge()
    print(f"  bridge entries (unique devanagari): {len(bridge)}")

    # Devanagari tokens that map to a known KG token (via Aksharantar)
    covered_devan = {
        dev for dev, roms in bridge.items() if any(r in kg for r in roms)
    }
    print(f"  Aksharantar-covered devanagari (intersects KG): {len(covered_devan)}")

    print("extracting Devanagari tokens from YouTube transcripts...")
    yt = extract_devan_tokens(YT_DIR)
    print(f"  unique Devanagari tokens in transcripts: {len(yt)}")
    print(f"  total Devanagari token occurrences: {sum(yt.values())}")

    covered = {t: n for t, n in yt.items() if t in covered_devan}
    novel = {t: n for t, n in yt.items() if t not in covered_devan}

    pct_covered = 100 * sum(covered.values()) / max(sum(yt.values()), 1)
    print(f"\ncovered-by-KG (via bridge): {len(covered)} tokens ({sum(covered.values())} occurrences, {pct_covered:.1f}%)")
    print(f"novel (not in KG):          {len(novel)} tokens ({sum(novel.values())} occurrences, {100-pct_covered:.1f}%)")

    print("\n=== TOP 30 NOVEL DEVANAGARI TOKENS (potential KG enrichment targets) ===")
    for tok, n in sorted(novel.items(), key=lambda x: -x[1])[:30]:
        print(f"  {tok:25s} x{n}")

    print("\n=== TOP 30 COVERED (KG already knows) ===")
    for tok, n in sorted(covered.items(), key=lambda x: -x[1])[:30]:
        print(f"  {tok:25s} x{n}")

    summary = {
        "kg_latin_tokens": len(kg),
        "bridge_unique_devanagari": len(bridge),
        "transcript_unique_devanagari": len(yt),
        "transcript_total_occurrences": sum(yt.values()),
        "covered_unique": len(covered),
        "novel_unique": len(novel),
        "coverage_occurrence_pct": round(pct_covered, 1),
        "top_novel": dict(sorted(novel.items(), key=lambda x: -x[1])[:100]),
        "top_covered": dict(sorted(covered.items(), key=lambda x: -x[1])[:100]),
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
