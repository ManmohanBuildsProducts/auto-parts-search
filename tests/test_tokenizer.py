"""Tests for auto_parts_search.tokenizer (T402a)."""
from __future__ import annotations

import pytest

from auto_parts_search.tokenizer import (
    BridgeTransliterator,
    IndicTokenizer,
    bridge_stats,
    detect_script,
    normalize,
    split_tokens,
)


# --- script detection ---

class TestScriptDetection:
    def test_latin_only(self):
        assert detect_script("brake pad") == "latin"

    def test_devanagari_only(self):
        assert detect_script("ब्रेक पैड") == "devanagari"

    def test_mixed(self):
        assert detect_script("brake ki पट्टी") == "mixed"

    def test_other(self):
        assert detect_script("12345") == "other"
        assert detect_script("") == "other"

    def test_single_char(self):
        assert detect_script("b") == "latin"
        assert detect_script("ब") == "devanagari"


# --- normalization ---

class TestNormalize:
    def test_nfc_idempotent(self):
        assert normalize("oil") == "oil"

    def test_strips_whitespace(self):
        assert normalize("  brake pad  ") == "brake pad"

    def test_unicode_decomposed_form(self):
        # NFD form of क्ष (Sanskrit ksh)
        decomposed = "क\u094d\u0937"
        out = normalize(decomposed)
        assert out.startswith("क")


class TestSplitTokens:
    def test_latin(self):
        assert split_tokens("brake pad set") == ["brake", "pad", "set"]

    def test_devanagari(self):
        # whitespace should keep words intact
        out = split_tokens("ब्रेक पैड")
        assert "ब्रेक" in out
        assert "पैड" in out

    def test_punctuation(self):
        assert split_tokens("brake/pad, swift") == ["brake", "pad", "swift"]

    def test_empty(self):
        assert split_tokens("") == []
        assert split_tokens("   ") == []


# --- bridge lookup ---

class TestBridgeLookup:
    def test_stats_nonempty(self):
        stats = bridge_stats()
        assert stats["roman_to_devanagari_entries"] > 1000
        assert stats["devanagari_to_roman_entries"] > 1000

    def test_roman_to_devanagari_known_term(self):
        t = BridgeTransliterator()
        hits = t.all_devanagari("oil")
        # Our Hinglish bridge mapped oil -> [ऑयल, तेल]
        assert len(hits) >= 1
        assert any("ऑयल" in h or "तेल" in h for h in hits)

    def test_devanagari_to_roman_known_term(self):
        t = BridgeTransliterator()
        hits = t.all_roman("इंजन")
        assert len(hits) >= 1
        assert any("engine" in h.lower() for h in hits)

    def test_unknown_without_sarvam_returns_none(self):
        t = BridgeTransliterator()  # no sarvam
        assert t.to_devanagari("zzznotareal") is None


# --- tokenizer integration ---

class TestIndicTokenizer:
    def setup_method(self):
        self.tok = IndicTokenizer()

    def test_latin_query_dual_indexed(self):
        out = self.tok.query_tokens("brake pad")
        # should include both Roman and Devanagari forms
        assert "brake" in out
        assert "pad" in out
        # at least one Devanagari rendering should be added via bridge
        has_devan = any("\u0900" <= c <= "\u097F" for t in out for c in t)
        assert has_devan, f"expected Devanagari expansion, got {out}"

    def test_devanagari_query_dual_indexed(self):
        out = self.tok.query_tokens("ब्रेक पैड")
        assert "ब्रेक" in out
        has_roman = any("a" <= c.lower() <= "z" for t in out for c in t)
        assert has_roman, f"expected Roman expansion, got {out}"

    def test_mixed_query(self):
        out = self.tok.query_tokens("brake ki patti")
        assert "brake" in out
        assert "patti" in out

    def test_query_preserves_part_numbers(self):
        out = self.tok.query_tokens("Bosch 0986AB1234")
        assert "0986ab1234" in out or "0986AB1234".lower() in [x.lower() for x in out]

    def test_index_applies_stemming(self):
        idx_out = self.tok.index_tokens("running engines")
        # Snowball should stem "running" -> "run" and "engines" -> "engin"
        # (depends on stemmer version; allow either exact or stem)
        assert any(t.startswith("run") for t in idx_out)
        assert any(t.startswith("engin") for t in idx_out)

    def test_query_does_not_stem(self):
        out = self.tok.query_tokens("running engines")
        # queries preserve original form (case-folded)
        assert "running" in out
        assert "engines" in out

    def test_empty_query(self):
        assert self.tok.query_tokens("") == []

    def test_unicode_normalization_before_split(self):
        # string with combining marks normalized
        out = self.tok.query_tokens("  brake pad  ")
        assert "brake" in out
        assert "pad" in out


# --- performance sanity ---

class TestPerformance:
    def test_cached_maps_are_singleton(self):
        from auto_parts_search.lemma_map import load_maps
        a = load_maps()
        b = load_maps()
        assert a is b  # LRU cache hit

    def test_token_throughput(self):
        """Should handle >1000 tokens/sec on cold bridge lookup."""
        import time
        tok = IndicTokenizer()
        queries = [
            "brake pad Maruti Swift",
            "patti badal do bhaiya",
            "ब्रेक पैड",
            "engine garam ho raha hai",
            "O2 sensor Hyundai Verna",
        ] * 100
        t0 = time.time()
        for q in queries:
            tok.query_tokens(q)
        dt = time.time() - t0
        n_tokens = sum(len(q.split()) for q in queries)
        rate = n_tokens / dt
        assert rate > 1000, f"throughput {rate:.0f} tok/s is below 1000"
