"""Tests for generate_listwise_data.py helpers."""
from unittest.mock import MagicMock, patch
import pytest

from scripts.generate_listwise_data import (
    build_query_prompt,
    parse_query_response,
    make_azure_client,
)


def test_build_query_prompt_contains_doc_title():
    prompt = build_query_prompt("Maruti Swift Rear Brake Pad - ATE OEM")
    assert "Maruti Swift Rear Brake Pad" in prompt
    assert "Hindi" in prompt
    assert "Hinglish" in prompt
    assert "brand" in prompt.lower() or "generic" in prompt.lower()


def test_parse_query_response_returns_6_queries():
    raw = """[
        "brake pad for Swift",
        "Swift ke liye brake pad",
        "Swift brake pad lagao",
        "Swift rear brake pad Romanized query",
        "rear braking noise Swift",
        "ATE brake pad Swift OEM"
    ]"""
    result = parse_query_response(raw)
    assert len(result) == 6
    assert all(isinstance(q, str) for q in result)


def test_parse_query_response_handles_truncated_json():
    raw = '["brake pad for Swift", "Swift ke liye'
    result = parse_query_response(raw)
    assert isinstance(result, list)


def test_parse_query_response_deduplicates():
    raw = '["same query", "same query", "different query"]'
    result = parse_query_response(raw)
    assert len(set(result)) == len(result)


from scripts.generate_listwise_data import normalize_teacher_scores


def test_normalize_teacher_scores_range():
    scores = [3.2, -1.5, 0.0, 7.8, 2.1]
    normed = normalize_teacher_scores(scores)
    assert abs(min(normed)) < 1e-6
    assert abs(max(normed) - 1.0) < 1e-6
    assert len(normed) == len(scores)


def test_normalize_teacher_scores_constant_input():
    scores = [2.0, 2.0, 2.0]
    normed = normalize_teacher_scores(scores)
    assert all(s == 0.0 for s in normed)
