"""Tests for SQLite knowledge graph storage.

See ADR 007.
"""
import json
import time
from pathlib import Path

import pytest

from auto_parts_search.graph_db import GraphDB


@pytest.fixture
def sample_graph():
    return {
        "metadata": {"version": "test", "sources": ["test"]},
        "nodes": [
            {
                "id": "system:engine",
                "node_type": "system",
                "name": "Engine",
                "aliases": ["motor", "engine assembly"],
                "provenance": {"source": "test"},
            },
            {
                "id": "part:piston",
                "node_type": "part",
                "name": "Piston",
                "aliases": ["piston assembly"],
                "provenance": {"source": "test"},
            },
            {
                "id": "part:brake_pad",
                "node_type": "part",
                "name": "Brake Pad",
                "aliases": ["disc brake pad", "brake pad set"],
                "provenance": {"source": "test"},
            },
            {
                "id": "symptom:engine_not_starting",
                "node_type": "symptom",
                "name": "Engine not starting",
                "provenance": {"source": "test"},
            },
        ],
        "edges": [
            {"source_id": "part:piston", "target_id": "system:engine",
             "edge_type": "in_system", "source": "test", "confidence": 1.0},
            {"source_id": "symptom:engine_not_starting", "target_id": "part:piston",
             "edge_type": "caused_by", "source": "test", "confidence": 0.8},
        ],
    }


@pytest.fixture
def db_path(tmp_path) -> Path:
    return tmp_path / "graph.db"


def test_init_and_load(db_path, sample_graph):
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        counts = db.counts()

    assert counts["nodes_total"] == 4
    assert counts["edges_total"] == 2
    assert counts["nodes_by_type"]["part"] == 2
    assert counts["nodes_by_type"]["system"] == 1
    assert counts["edges_by_type"]["in_system"] == 1


def test_node_lookup(db_path, sample_graph):
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        node = db.node("part:piston")
        assert node is not None
        assert node["name"] == "Piston"
        assert db.node("nonexistent") is None


def test_parts_in_system(db_path, sample_graph):
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        parts = db.parts_in_system("system:engine")
    assert len(parts) == 1
    assert parts[0]["id"] == "part:piston"


def test_symptoms_for_part(db_path, sample_graph):
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        symptoms = db.symptoms_for_part("part:piston")
    assert len(symptoms) == 1
    assert symptoms[0]["id"] == "symptom:engine_not_starting"


def test_fts_search(db_path, sample_graph):
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        results = db.search("brake")
    assert any(r["id"] == "part:brake_pad" for r in results)


def test_idempotent_rebuild(db_path, sample_graph):
    """Loading twice must not duplicate rows."""
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        db.load_from_graph_dict(sample_graph)
        counts = db.counts()
    assert counts["nodes_total"] == 4
    assert counts["edges_total"] == 2


def test_lookup_performance(db_path, sample_graph):
    """Indexed neighbor lookup should be sub-millisecond on a tiny graph.

    Smoke test for the index — real perf test is against the full 2.6K-node graph.
    """
    with GraphDB(db_path) as db:
        db.init_schema()
        db.load_from_graph_dict(sample_graph)
        start = time.perf_counter()
        for _ in range(1000):
            db.parts_in_system("system:engine")
        elapsed_ms = (time.perf_counter() - start) * 1000
    # 1000 lookups should complete in well under a second
    assert elapsed_ms < 1000, f"1000 lookups took {elapsed_ms:.1f}ms"
