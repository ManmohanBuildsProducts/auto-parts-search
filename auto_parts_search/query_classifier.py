"""Lightweight query classifier for hybrid retrieval routing.

Decides fusion weights between BM25 and the v3 embedding based on query
shape. Rules (in precedence order):

  1. part_number   -> alphanumeric token of 5+ chars with >=2 digits
  2. hindi_hinglish -> Devanagari OR common Hindi connectors (ka, ki, do, bhaiya, wala...)
  3. symptom       -> symptom markers (garam, awaaz, problem, ho raha, jhatka, kharab...)
  4. brand_as_generic -> starts with known-brand + part category
  5. exact_english (default)

Output includes fusion weights — BM25 vs embedding — tuned for each class.
Weights are testable defaults, not learned; tuneable via the WEIGHTS dict.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

QueryClass = Literal[
    "part_number", "hindi_hinglish", "symptom", "brand_as_generic", "exact_english"
]

# Fusion weights: (bm25, embedding). Sum to 1.0.
#   part_number:       BM25 dominant — exact string match beats semantic
#   symptom:           embedding dominant — needs semantic understanding
#   brand_as_generic:  embedding dominant — semantic linking brand -> category
#   hindi_hinglish:    balanced — both help
#   exact_english:     balanced; BM25 still strong for canonical terms
WEIGHTS: dict[QueryClass, tuple[float, float]] = {
    # Tuned 2026-04-14 via joint-pool graded bench on dev-149:
    # initial (0.5/0.5) hybrid tied v3 overall but regressed hindi/symptom/misspelled by 4-5%.
    # Dropping BM25 weight further on those 3 classes recovers without losing part_number/brand gains.
    "part_number": (0.80, 0.20),
    "symptom": (0.10, 0.90),
    "brand_as_generic": (0.30, 0.70),
    "hindi_hinglish": (0.20, 0.80),
    "exact_english": (0.50, 0.50),
}

# Heuristic resources
_DEVAN_RE = re.compile(r"[\u0900-\u097F]")
_HINDI_CONNECTOR_RE = re.compile(
    r"\b(ka|ki|ke|ko|me|mein|se|par|wala|wali|bhaiya|bhai|badal|do|hai|hain|nahi|nahin|kya|kaunsa|kaise)\b",
    re.I,
)
_SYMPTOM_RE = re.compile(
    r"\b("
    r"garam|thanda|awaaz|awaj|problem|ho\s+raha|ho\s+rahi|kharab|"
    r"jhatka|jhatke|mileage|band|start|nahi|nikal|leak|noise|smoke|dhuaa|"
    r"dhuan|safed|jamega|chalta|overheat|patak|kamp|wobble|seeti|khar-khar"
    r")\b",
    re.I,
)
_BRANDS = {
    "bosch", "mrf", "exide", "castrol", "mobil", "denso", "monroe", "ngk",
    "dunlop", "valeo", "brembo", "amaron", "skf", "bridgestone", "apollo",
    "ceat", "michelin", "yokohama", "gates", "bosch", "delphi", "lucas",
    "minda", "motul", "shell", "hp", "servo", "liqui", "gulf",
}
_PART_NUMBER_RE = re.compile(r"^[A-Za-z0-9]{5,}$")


@dataclass
class Classification:
    query_class: QueryClass
    bm25_weight: float
    embedding_weight: float
    evidence: str     # short human-readable reason


def classify(query: str) -> Classification:
    q = query.strip()
    if not q:
        return Classification("exact_english", *WEIGHTS["exact_english"], evidence="empty")

    tokens = q.split()

    # 1. part_number — single alnum token with digits
    if len(tokens) == 1 and _PART_NUMBER_RE.match(tokens[0]) and any(c.isdigit() for c in tokens[0]):
        if sum(c.isdigit() for c in tokens[0]) >= 2:
            return Classification("part_number", *WEIGHTS["part_number"], evidence=f"single alnum with digits: {tokens[0]}")
    # Multi-token like "Bosch 0986AB1234" — still part_number pattern
    for tok in tokens:
        if _PART_NUMBER_RE.match(tok) and sum(c.isdigit() for c in tok) >= 3 and any(c.isalpha() for c in tok):
            return Classification("part_number", *WEIGHTS["part_number"], evidence=f"alnum part-number token: {tok}")

    # 2. hindi_hinglish — Devanagari present or Hindi connectors
    if _DEVAN_RE.search(q):
        return Classification("hindi_hinglish", *WEIGHTS["hindi_hinglish"], evidence="devanagari present")
    if _HINDI_CONNECTOR_RE.search(q):
        return Classification("hindi_hinglish", *WEIGHTS["hindi_hinglish"], evidence="hindi connector word")

    # 3. symptom — symptom markers
    if _SYMPTOM_RE.search(q):
        return Classification("symptom", *WEIGHTS["symptom"], evidence="symptom marker")

    # 4. brand_as_generic — starts with a known brand
    first_low = tokens[0].lower()
    if first_low in _BRANDS:
        return Classification("brand_as_generic", *WEIGHTS["brand_as_generic"], evidence=f"brand prefix: {first_low}")

    # 5. default
    return Classification("exact_english", *WEIGHTS["exact_english"], evidence="default")
