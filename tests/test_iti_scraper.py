"""Tests for ITI syllabus diagnostic chain extraction."""
import json
from pathlib import Path

import pytest

# Add project root to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.iti_scraper import (
    ITI_SYLLABI,
    STRUCTURED_DIAGNOSTICS,
    parse_iti_diagnostics,
    _classify_system,
    _extract_parts,
    _make_id,
    _normalize_text,
)
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR


class TestStructuredDiagnostics:
    """Tests for the hardcoded diagnostic chains."""

    def test_all_trades_have_chains(self):
        """Every trade in ITI_SYLLABI should have structured diagnostics."""
        for trade_key in ITI_SYLLABI:
            assert trade_key in STRUCTURED_DIAGNOSTICS, f"Missing diagnostics for {trade_key}"
            assert len(STRUCTURED_DIAGNOSTICS[trade_key]) >= 3, (
                f"Trade {trade_key} has too few chains: {len(STRUCTURED_DIAGNOSTICS[trade_key])}"
            )

    def test_chain_structure(self):
        """Every chain should have required fields."""
        for trade_key, chains in STRUCTURED_DIAGNOSTICS.items():
            for i, chain in enumerate(chains):
                assert "symptom" in chain, f"{trade_key}[{i}] missing symptom"
                assert "system" in chain, f"{trade_key}[{i}] missing system"
                assert "diagnosis_steps" in chain, f"{trade_key}[{i}] missing diagnosis_steps"
                assert "related_parts" in chain, f"{trade_key}[{i}] missing related_parts"
                assert len(chain["symptom"]) > 10, f"{trade_key}[{i}] symptom too short"
                assert len(chain["diagnosis_steps"]) >= 3, (
                    f"{trade_key}[{i}] needs at least 3 diagnosis steps, has {len(chain['diagnosis_steps'])}"
                )
                assert len(chain["related_parts"]) >= 1, (
                    f"{trade_key}[{i}] needs at least 1 related part"
                )

    def test_no_duplicate_symptoms(self):
        """No duplicate symptoms across all trades."""
        all_symptoms = []
        for chains in STRUCTURED_DIAGNOSTICS.values():
            for chain in chains:
                all_symptoms.append(chain["symptom"].lower())
        assert len(all_symptoms) == len(set(all_symptoms)), "Duplicate symptoms found"

    def test_minimum_chain_count(self):
        """Should have at least 85 structured chains (before PDF extraction)."""
        total = sum(len(chains) for chains in STRUCTURED_DIAGNOSTICS.values())
        assert total >= 85, f"Only {total} structured chains, need at least 85"


class TestHelpers:
    """Tests for helper functions."""

    def test_classify_system_engine(self):
        assert _classify_system("engine overheating cylinder piston") == "engine"

    def test_classify_system_braking(self):
        assert _classify_system("brake pad replacement disc brake ABS") == "braking_system"

    def test_classify_system_ev(self):
        assert _classify_system("battery management BMS motor controller") == "ev_system"

    def test_classify_system_unknown(self):
        assert _classify_system("random unrelated text") == "general"

    def test_extract_parts_common(self):
        parts = _extract_parts("Check the spark plug and fuel filter condition")
        assert "Spark Plug" in parts
        assert "Fuel Filter" in parts

    def test_extract_parts_empty(self):
        parts = _extract_parts("nothing relevant here")
        assert parts == []

    def test_make_id(self):
        assert _make_id("Engine not starting") == "engine_not_starting"

    def test_make_id_truncation(self):
        long_symptom = "Very long symptom description " * 5
        result = _make_id(long_symptom)
        assert len(result) <= 60

    def test_normalize_text(self):
        assert "Electrical" in _normalize_text("E lectrical system fault")
        assert "Mechanic" in _normalize_text("Mecha nic training")


class TestFullPipeline:
    """Tests for the full parsing pipeline."""

    @pytest.fixture
    def chains(self):
        """Parse all chains (uses PDFs if available)."""
        return parse_iti_diagnostics()

    def test_minimum_100_chains(self, chains):
        """Must produce at least 100 diagnostic chains."""
        assert len(chains) >= 100, f"Only {len(chains)} chains, need at least 100"

    def test_all_chains_have_ids(self, chains):
        """Every chain must have a unique ID."""
        ids = [c["id"] for c in chains]
        assert all(id.startswith("diag:") for id in ids)
        assert len(ids) == len(set(ids)), "Duplicate chain IDs found"

    def test_all_chains_have_required_fields(self, chains):
        """Every chain must have all required fields."""
        required = {"id", "symptom", "system", "diagnosis_steps", "related_parts",
                    "source_trade", "vehicle_type", "confidence"}
        for chain in chains:
            missing = required - set(chain.keys())
            assert not missing, f"Chain {chain['id']} missing fields: {missing}"

    def test_systems_coverage(self, chains):
        """Should cover at least 10 different vehicle systems."""
        systems = set(c["system"] for c in chains)
        assert len(systems) >= 10, f"Only {len(systems)} systems covered: {systems}"

    def test_vehicle_type_coverage(self, chains):
        """Should cover multiple vehicle types."""
        vtypes = set(c["vehicle_type"] for c in chains)
        assert "LMV/HMV" in vtypes
        assert "2W" in vtypes
        assert "tractor" in vtypes
        assert "EV" in vtypes

    def test_trade_coverage(self, chains):
        """Should have chains from all 6 trades."""
        trades = set(c["source_trade"] for c in chains)
        assert len(trades) >= 6, f"Only {len(trades)} trades represented: {trades}"

    def test_high_confidence_chains_have_steps(self, chains):
        """High-confidence (structured) chains should have diagnosis steps."""
        structured = [c for c in chains if c["confidence"] >= 0.8]
        for chain in structured:
            assert len(chain["diagnosis_steps"]) >= 3, (
                f"Structured chain {chain['id']} has only {len(chain['diagnosis_steps'])} steps"
            )


class TestOutputFile:
    """Tests for the saved JSON output."""

    @pytest.fixture
    def output_data(self):
        output_path = KNOWLEDGE_GRAPH_DIR / "iti_diagnostics.json"
        if not output_path.exists():
            pytest.skip("Output file not generated yet")
        with open(output_path) as f:
            return json.load(f)

    def test_output_has_metadata(self, output_data):
        assert "metadata" in output_data
        assert "total_chains" in output_data["metadata"]
        assert output_data["metadata"]["total_chains"] >= 100

    def test_output_has_chains(self, output_data):
        assert "chains" in output_data
        assert len(output_data["chains"]) >= 100

    def test_output_metadata_consistency(self, output_data):
        """Metadata chain count should match actual chain count."""
        assert output_data["metadata"]["total_chains"] == len(output_data["chains"])
