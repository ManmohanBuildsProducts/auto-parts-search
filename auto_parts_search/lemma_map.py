"""Bidirectional Roman <-> Devanagari lemma map for auto-parts.

Merges two data sources:
  1. data/external/processed/kg_hinglish_bridge.jsonl  — DeepSeek-enriched
     KG terms (2,463 latin terms -> up to 3 Devanagari renderings each).
  2. data/external/processed/ai4bharat_aksharantar_auto.jsonl — curated
     AI4Bharat transliteration pairs filtered to auto-domain (3,660 pairs).

Builds two in-memory dicts at module import:
  ROMAN_TO_DEVAN: dict[str, list[str]]    # "oil" -> ["ऑयल", "तेल"]
  DEVAN_TO_ROMAN: dict[str, list[str]]    # "ऑयल" -> ["oil"]

Loads once. Safe to import anywhere.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

_HINGLISH = Path(__file__).parent.parent / "data/external/processed/kg_hinglish_bridge.jsonl"
_AKSHARANTAR = Path(__file__).parent.parent / "data/external/processed/ai4bharat_aksharantar_auto.jsonl"

# Token-level stoplist: words the Hinglish bridge shouldn't canonicalize.
# These are things like "material", "monitoring" — generic English that
# isn't auto-specific and leaked into our KG via HSN taxonomy bloat.
_STOPLIST: set[str] = {
    "heading", "gutkha", "elements", "photovoltaic", "filament", "tandem",
    "sheesha", "reg", "community", "horizontal", "monitoring", "maintenance",
    "accessories", "clearance", "resistance", "combination", "constant",
    "stability", "prevention", "material", "components", "devices", "points",
    "distribution", "appliances",
}


def _has_devanagari(s: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", s))


def _build_maps() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    roman_to_devan: dict[str, set[str]] = defaultdict(set)
    devan_to_roman: dict[str, set[str]] = defaultdict(set)

    if _HINGLISH.exists():
        for line in _HINGLISH.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            term = r["term"].strip().lower()
            if not term or term in _STOPLIST:
                continue
            for rend in r.get("renderings", []):
                rend = rend.strip()
                if rend and _has_devanagari(rend):
                    roman_to_devan[term].add(rend)
                    devan_to_roman[rend].add(term)

    if _AKSHARANTAR.exists():
        for line in _AKSHARANTAR.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            rom = r.get("roman", "").strip().lower()
            dev = r.get("devanagari", "").strip()
            if not rom or not dev or rom in _STOPLIST:
                continue
            if not _has_devanagari(dev):
                continue
            roman_to_devan[rom].add(dev)
            devan_to_roman[dev].add(rom)

    return (
        {k: sorted(v) for k, v in roman_to_devan.items()},
        {k: sorted(v) for k, v in devan_to_roman.items()},
    )


@lru_cache(maxsize=1)
def load_maps() -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    return _build_maps()


def roman_to_devanagari(token: str) -> list[str]:
    r2d, _ = load_maps()
    return r2d.get(token.strip().lower(), [])


def devanagari_to_roman(token: str) -> list[str]:
    _, d2r = load_maps()
    return d2r.get(token.strip(), [])


def is_known(token: str) -> bool:
    """True iff the token is in either direction of the bridge."""
    t_low = token.strip().lower()
    r2d, d2r = load_maps()
    return t_low in r2d or token.strip() in d2r
