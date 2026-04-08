"""Tests for the 200-query evaluation benchmark."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from training.benchmark import generate_benchmark


EXPECTED_COUNTS = {
    "exact_english": 35,
    "hindi_hinglish": 35,
    "misspelled": 30,
    "symptom": 35,
    "part_number": 30,
    "brand_as_generic": 30,
}

VALID_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_TYPES = set(EXPECTED_COUNTS.keys())
TOLERANCE = 2


def test_total_count():
    queries = generate_benchmark()
    assert len(queries) >= 195, f"Expected >= 195 queries, got {len(queries)}"


def test_type_counts():
    queries = generate_benchmark()
    from collections import Counter
    counts = Counter(q.query_type for q in queries)
    for qtype, expected in EXPECTED_COUNTS.items():
        actual = counts.get(qtype, 0)
        assert abs(actual - expected) <= TOLERANCE, (
            f"{qtype}: expected {expected} +/-{TOLERANCE}, got {actual}"
        )


def test_all_queries_have_text():
    queries = generate_benchmark()
    for i, q in enumerate(queries):
        assert q.query and q.query.strip(), f"Query {i} has empty query text"


def test_all_queries_have_expected_parts():
    queries = generate_benchmark()
    for i, q in enumerate(queries):
        assert len(q.expected_parts) >= 1, (
            f"Query {i} ({q.query!r}) has no expected_parts"
        )


def test_valid_difficulty():
    queries = generate_benchmark()
    for i, q in enumerate(queries):
        assert q.difficulty in VALID_DIFFICULTIES, (
            f"Query {i} ({q.query!r}) has invalid difficulty: {q.difficulty!r}"
        )


def test_valid_query_types():
    queries = generate_benchmark()
    for i, q in enumerate(queries):
        assert q.query_type in VALID_TYPES, (
            f"Query {i} ({q.query!r}) has invalid query_type: {q.query_type!r}"
        )


def test_no_duplicate_queries():
    queries = generate_benchmark()
    seen = set()
    for i, q in enumerate(queries):
        assert q.query not in seen, (
            f"Duplicate query at index {i}: {q.query!r}"
        )
        seen.add(q.query)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
