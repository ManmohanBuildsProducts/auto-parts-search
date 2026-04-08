"""Tests for training.vocabulary_pairs module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from training.vocabulary_pairs import generate_vocabulary_pairs, save_pairs


def _get_pairs():
    """Cache pairs across tests."""
    if not hasattr(_get_pairs, "_cache"):
        _get_pairs._cache = generate_vocabulary_pairs()
    return _get_pairs._cache


class TestVocabularyPairCounts:
    def test_at_least_500_positive_pairs(self):
        pairs = _get_pairs()
        positive = [p for p in pairs if p.label == 1.0]
        assert len(positive) >= 500, f"Expected >=500 positive pairs, got {len(positive)}"

    def test_at_least_1000_negative_pairs(self):
        pairs = _get_pairs()
        negative = [p for p in pairs if p.label == 0.0]
        assert len(negative) >= 1000, f"Expected >=1000 negative pairs, got {len(negative)}"


class TestVocabularyPairTypes:
    def test_all_pair_types_present(self):
        pairs = _get_pairs()
        types = {p.pair_type for p in pairs}
        expected = {"synonym", "misspelling", "symptom", "brand_generic", "negative"}
        assert expected.issubset(types), f"Missing pair types: {expected - types}"

    def test_synonym_pairs_exist(self):
        pairs = _get_pairs()
        synonyms = [p for p in pairs if p.pair_type == "synonym"]
        assert len(synonyms) > 0

    def test_misspelling_pairs_exist(self):
        pairs = _get_pairs()
        misspellings = [p for p in pairs if p.pair_type == "misspelling"]
        assert len(misspellings) > 0

    def test_symptom_pairs_exist(self):
        pairs = _get_pairs()
        symptoms = [p for p in pairs if p.pair_type == "symptom"]
        assert len(symptoms) > 0

    def test_brand_generic_pairs_exist(self):
        pairs = _get_pairs()
        brand = [p for p in pairs if p.pair_type == "brand_generic"]
        assert len(brand) > 0


class TestVocabularyPairQuality:
    def test_labels_are_binary(self):
        pairs = _get_pairs()
        for p in pairs:
            assert p.label in (0.0, 1.0), f"Invalid label {p.label} for pair ({p.text_a}, {p.text_b})"

    def test_no_empty_text_a(self):
        pairs = _get_pairs()
        for p in pairs:
            assert p.text_a.strip(), f"Empty text_a in pair: {p}"

    def test_no_empty_text_b(self):
        pairs = _get_pairs()
        for p in pairs:
            assert p.text_b.strip(), f"Empty text_b in pair: {p}"

    def test_positive_pairs_have_positive_label(self):
        pairs = _get_pairs()
        for p in pairs:
            if p.pair_type != "negative":
                assert p.label == 1.0, f"Non-negative pair has label {p.label}: {p.pair_type}"

    def test_negative_pairs_have_zero_label(self):
        pairs = _get_pairs()
        for p in pairs:
            if p.pair_type == "negative":
                assert p.label == 0.0, f"Negative pair has label {p.label}"


class TestSavePairs:
    def test_save_and_load(self, tmp_path):
        pairs = generate_vocabulary_pairs()
        output = tmp_path / "test_pairs.jsonl"
        save_pairs(pairs, output)

        assert output.exists()
        lines = output.read_text().strip().split("\n")
        assert len(lines) == len(pairs)

        import json
        first = json.loads(lines[0])
        assert "text_a" in first
        assert "text_b" in first
        assert "label" in first
        assert "pair_type" in first
