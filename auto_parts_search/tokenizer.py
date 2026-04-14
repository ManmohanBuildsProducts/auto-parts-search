"""Search tokenizer for Hindi / Hinglish / Devanagari auto-parts queries.

Pipeline (per ADR 010, revised after T402a research audit):

  Index-time (catalog):
    normalize Unicode NFC
    -> script-detect per token
    -> Devanagari: indic-nlp tokenize + stem
    -> Latin: lowercase + Snowball English stem
    -> dual-index original + transliterated

  Query-time:
    normalize Unicode NFC
    -> whitespace/punct tokenize
    -> per-token bridge lookup (bidirectional; KG Hinglish + Aksharantar)
    -> bridge-miss fallback: Sarvam Transliterate API (cached)
    -> no stemming on query side (preserves part-number exact match)

Components are composable: a call-site that only needs transliteration can
instantiate `BridgeTransliterator` directly without pulling in stemming.
"""
from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable

from auto_parts_search.lemma_map import (
    devanagari_to_roman,
    load_maps,
    roman_to_devanagari,
)

# ---------- script detection ----------

_DEVAN_RE = re.compile(r"[\u0900-\u097F]")
_LATIN_RE = re.compile(r"[A-Za-z]")
_TOKEN_SPLIT = re.compile(r"[^\w\u0900-\u097F]+", re.UNICODE)


def detect_script(text: str) -> str:
    """Return 'devanagari', 'latin', 'mixed', or 'other'."""
    has_dev = bool(_DEVAN_RE.search(text))
    has_lat = bool(_LATIN_RE.search(text))
    if has_dev and has_lat:
        return "mixed"
    if has_dev:
        return "devanagari"
    if has_lat:
        return "latin"
    return "other"


# ---------- normalization + tokenization ----------

def normalize(text: str) -> str:
    """Unicode NFC, collapse whitespace. Safe for Devanagari + Latin."""
    return unicodedata.normalize("NFC", text).strip()


def split_tokens(text: str) -> list[str]:
    """Whitespace + punctuation tokenizer. Keeps Devanagari compounds intact."""
    out = [t for t in _TOKEN_SPLIT.split(text) if t]
    return out


# ---------- Sarvam transliterate (bridge-miss fallback) ----------

_SARVAM_URL = "https://api.sarvam.ai/transliterate"


@dataclass
class SarvamTransliterator:
    """Neural fallback for tokens not in our bridges. In-memory cached."""

    api_key: str | None = None
    timeout: float = 8.0
    cache: dict[tuple[str, str, str], str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.environ.get("SARVAM_API_KEY")

    def transliterate(
        self, text: str, target_lang: str = "hi-IN", source_lang: str | None = None
    ) -> str | None:
        """Transliterate via Sarvam /transliterate API.

        target_lang='hi-IN' -> Devanagari; target_lang='en-IN' -> Latin.
        source_lang: required by Sarvam API. Auto-inferred from script if not given.
        Returns None on any failure. Cached per (text, source, target).
        """
        # Auto-detect source language if not provided
        if not source_lang:
            # Heuristic: Devanagari input -> hi-IN source; else en-IN
            src = "hi-IN" if any("\u0900" <= c <= "\u097F" for c in text) else "en-IN"
        else:
            src = source_lang
        key = (text, src, target_lang)
        if key in self.cache:
            return self.cache[key]
        if not self.api_key:
            return None
        try:
            import requests
        except ImportError:
            return None
        try:
            body = {
                "input": text,
                "source_language_code": src,
                "target_language_code": target_lang,
                "numerals_format": "international",
                "spoken_form_numerals_language": "english",
            }
            r = requests.post(
                _SARVAM_URL,
                headers={"api-subscription-key": self.api_key, "Content-Type": "application/json"},
                json=body,
                timeout=self.timeout,
            )
            r.raise_for_status()
            out = (r.json() or {}).get("transliterated_text", "").strip()
            if out:
                self.cache[key] = out
                return out
        except Exception:
            return None
        return None


# ---------- transliteration facade ----------

@dataclass
class BridgeTransliterator:
    """Bridge-first transliterator. Returns canonical forms per direction.

    Lookup order:
      1. In-memory lemma_map (KG Hinglish bridge + Aksharantar, ~5k entries).
      2. Sarvam API fallback if `sarvam` is provided AND bridge misses.

    Methods return the top-1 transliteration; `all_variants()` returns all
    bridge entries (useful for query expansion / dual-indexing).
    """

    sarvam: SarvamTransliterator | None = None

    def to_devanagari(self, token: str) -> str | None:
        if not token:
            return None
        hits = roman_to_devanagari(token)
        if hits:
            return hits[0]
        if self.sarvam:
            return self.sarvam.transliterate(token, target_lang="hi-IN")
        return None

    def to_roman(self, token: str) -> str | None:
        if not token:
            return None
        hits = devanagari_to_roman(token)
        if hits:
            return hits[0]
        if self.sarvam:
            return self.sarvam.transliterate(token, target_lang="en-IN")
        return None

    def all_devanagari(self, token: str) -> list[str]:
        hits = roman_to_devanagari(token)
        if hits:
            return hits
        if self.sarvam:
            v = self.sarvam.transliterate(token, target_lang="hi-IN")
            return [v] if v else []
        return []

    def all_roman(self, token: str) -> list[str]:
        hits = devanagari_to_roman(token)
        if hits:
            return hits
        if self.sarvam:
            v = self.sarvam.transliterate(token, target_lang="en-IN")
            return [v] if v else []
        return []


# ---------- stemmer facade (index-time only, per research audit) ----------

class _StemmerFacade:
    """Wraps Snowball English + indic-nlp-library Hindi stemmer with lazy load."""

    def __init__(self) -> None:
        self._en = None
        self._hi_loaded = False

    def _ensure_en(self):
        if self._en is None:
            import snowballstemmer
            self._en = snowballstemmer.stemmer("english")
        return self._en

    def _ensure_hi(self):
        if not self._hi_loaded:
            # indic-nlp-library's Hindi stemmer is a simple suffix-stripping utility
            # Lazy-imported to avoid startup cost when only English is used.
            try:
                from indicnlp.morph.unsupervised_morph import UnsupervisedMorphAnalyzer  # noqa
                self._hi_loaded = True
            except Exception:
                self._hi_loaded = True  # degrade to rule-based below
        return None

    def stem_english(self, token: str) -> str:
        if not token:
            return token
        return self._ensure_en().stemWord(token.lower())

    def stem_hindi(self, token: str) -> str:
        """Rule-based suffix stripping for Hindi (common inflectional endings).

        Light-touch; real morphological analysis deferred. Part-name catalogs
        barely inflect so this is precision-first.
        """
        if not token:
            return token
        # Strip common Hindi inflectional suffixes
        for suffix in ("ियाँ", "ियों", "ियां", "ोंको", "ाओं", "ोंमें", "ोंसे",
                       "कर", "ाना", "ेगा", "ेगी", "ेंगे", "ूंगा", "ूंगी",
                       "ाई", "ाओ", "ोंका", "ोंकी", "ोंके",
                       "ों", "ें", "ियो", "ाएं", "ाएँ", "ाया", "ायी", "ाये",
                       "ना", "नी", "ने", "ती", "ते", "ता", "ी", "े", "ो",
                       "ाँ", "ां", "ं"):
            if token.endswith(suffix) and len(token) - len(suffix) >= 2:
                return token[: -len(suffix)]
        return token


# ---------- main tokenizer ----------

@dataclass
class IndicTokenizer:
    """Composable Hindi/Hinglish tokenizer for Meilisearch-style BM25 pipelines.

    Two call sites:
      - index_tokens(doc) -> tokens to index (stems applied; dual-script expansion)
      - query_tokens(q)  -> tokens to query with (no stem; bridge expansion)
    """

    transliterator: BridgeTransliterator = field(default_factory=BridgeTransliterator)
    stemmer: _StemmerFacade = field(default_factory=_StemmerFacade)

    def index_tokens(self, text: str) -> list[str]:
        """Tokens for catalog-side indexing. Applies stemming + dual-script expansion.

        Uses ALL known bridge variants per token so the index covers every
        common catalog spelling (e.g. pad -> [पद, पैड]).
        """
        t = normalize(text)
        raw = split_tokens(t)
        out: list[str] = []
        for tok in raw:
            script = detect_script(tok)
            if script == "devanagari":
                stem = self.stemmer.stem_hindi(tok)
                out.append(stem)
                for rom in self.transliterator.all_roman(tok):
                    out.append(rom.lower())
            elif script == "latin":
                low = tok.lower()
                out.append(self.stemmer.stem_english(low))
                # also include unstemmed lowercase for exact-match recall
                if self.stemmer.stem_english(low) != low:
                    out.append(low)
                for dev in self.transliterator.all_devanagari(low):
                    out.append(dev)
            else:
                out.append(tok.lower())
        # dedup preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for t in out:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        return uniq

    def query_tokens(self, text: str) -> list[str]:
        """Tokens for query-side. No stemming (preserves part numbers).

        Emits ALL known bridge variants per token (not just top-1) so BM25
        matches across catalog spellings + Aksharantar romanizations.
        """
        t = normalize(text)
        raw = split_tokens(t)
        out: list[str] = []
        for tok in raw:
            script = detect_script(tok)
            if script == "devanagari":
                out.append(tok)
                for rom in self.transliterator.all_roman(tok):
                    out.append(rom.lower())
            elif script == "latin":
                low = tok.lower()
                out.append(low)
                for dev in self.transliterator.all_devanagari(low):
                    out.append(dev)
            else:
                out.append(tok.lower())
        # Dedup preserving order
        seen: set[str] = set()
        uniq: list[str] = []
        for t in out:
            if t not in seen:
                seen.add(t)
                uniq.append(t)
        return uniq


# ---------- stats ----------

def bridge_stats() -> dict:
    """Diagnostic: how big are our bridges?"""
    r2d, d2r = load_maps()
    return {
        "roman_to_devanagari_entries": len(r2d),
        "devanagari_to_roman_entries": len(d2r),
        "sample_r2d": dict(list(r2d.items())[:3]),
        "sample_d2r": dict(list(d2r.items())[:3]),
    }
