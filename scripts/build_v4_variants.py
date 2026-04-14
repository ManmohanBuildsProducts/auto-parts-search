"""Build three v4 training-pair variants for A/B/C ablation.

Variant A (YT only):          v3 positives + 376 YT natural-speech pairs
Variant B (A + Aksharantar):  A + filtered AUTO-only Aksharantar pairs (~3K)
Variant C (B + Hinglish):     B + KG Hinglish-bridge synonym pairs (~4.9K)

All pairs get label=1.0 (positives for MNR loss). Same schema as golden-v2:
  {"text_a": str, "text_b": str, "label": 1.0, "pair_type": str, "source": str}

Outputs:
  data/external/processed/v4_variants/v4a.jsonl
  data/external/processed/v4_variants/v4b.jsonl
  data/external/processed/v4_variants/v4c.jsonl
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

GOLDEN_V2 = Path("data/training/golden/all_pairs_v2.jsonl")
YT = Path("data/external/processed/yt_pairs_v4_clean.jsonl")
AKS_AUDIT = Path("data/external/processed/aksharantar_audit.jsonl")  # subset; not used
AKS_FULL = Path("data/external/processed/ai4bharat_aksharantar_auto.jsonl")
HINGLISH = Path("data/external/processed/kg_hinglish_bridge.jsonl")

OUT = Path("data/external/processed/v4_variants")
OUT.mkdir(parents=True, exist_ok=True)

# A single NOISE-filter heuristic derived from audit: drop pairs whose
# roman token is a known noise word (from the audit 16% noise bucket).
# Conservative list — better to keep a borderline than drop legit.
AKS_NOISE_STOPLIST = {
    "heading", "gutkha", "elements", "photovoltaic", "filament", "tandem",
    "sheesha", "reg", "inline", "race", "separator", "push", "roll",
    "centrifugal", "community", "horizontal", "monitoring", "maintenance",
    "accessories", "clearance", "resistance", "combination", "constant",
    "stability", "prevention", "interior", "exterior", "material",
    "components", "devices", "points", "transformers", "distribution",
    "engagement", "appliances",
}


def load_v3_positives() -> list[dict]:
    """The 7,828 label==1.0 positives from golden-v2."""
    out = []
    for line in GOLDEN_V2.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        if r.get("label", 1.0) >= 1.0:
            out.append(r)
    return out


def load_yt_pairs() -> list[dict]:
    """376 clean YT natural-speech pairs."""
    out = []
    for line in YT.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        out.append({
            "text_a": r["text_a"],
            "text_b": r["text_b"],
            "label": 1.0,
            "pair_type": "yt_mechanic_speech",
            "source": r.get("source", "yt_pilot"),
        })
    return out


def load_aksharantar_auto() -> list[dict]:
    """Full Aksharantar auto set minus noise stopwords."""
    out = []
    kept = dropped = 0
    for line in AKS_FULL.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        rom = r["roman"].strip().lower()
        if rom in AKS_NOISE_STOPLIST:
            dropped += 1
            continue
        out.append({
            "text_a": rom,
            "text_b": r["devanagari"].strip(),
            "label": 1.0,
            "pair_type": "aksharantar_synonym",
            "source": "ai4bharat_aksharantar",
        })
        kept += 1
    print(f"  aksharantar: kept {kept}, dropped {dropped} noise")
    return out


def load_hinglish_bridge() -> list[dict]:
    """KG Hinglish bridge: one pair per (term, rendering)."""
    out = []
    for line in HINGLISH.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line)
        term = r["term"].strip()
        for rend in r["renderings"]:
            rend = rend.strip()
            if rend and term:
                out.append({
                    "text_a": term,
                    "text_b": rend,
                    "label": 1.0,
                    "pair_type": "hinglish_bridge",
                    "source": "deepseek_kg_enrichment",
                })
    return out


def dedup(pairs: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for p in pairs:
        key = (p["text_a"].strip().lower(), p["text_b"].strip().lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def write_variant(name: str, pairs: list[dict]) -> None:
    fp = OUT / f"{name}.jsonl"
    with fp.open("w") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    c = Counter(p["pair_type"] for p in pairs)
    print(f"\n{name}: {len(pairs)} pairs -> {fp}")
    for t, n in c.most_common():
        print(f"  {t}: {n}")


def main() -> None:
    print("loading components...")
    v3 = load_v3_positives()
    print(f"  v3 positives: {len(v3)}")
    yt = load_yt_pairs()
    print(f"  yt pairs: {len(yt)}")
    aks = load_aksharantar_auto()
    print(f"  aksharantar: {len(aks)}")
    hin = load_hinglish_bridge()
    print(f"  hinglish bridge: {len(hin)}")

    v4a = dedup(v3 + yt)
    v4b = dedup(v3 + yt + aks)
    v4c = dedup(v3 + yt + aks + hin)

    write_variant("v4a", v4a)
    write_variant("v4b", v4b)
    write_variant("v4c", v4c)


if __name__ == "__main__":
    main()
