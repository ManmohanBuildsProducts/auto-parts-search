"""Tests for ASDC scraper — PDF parsing logic, no real HTTP requests."""
import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.asdc_scraper import (
    parse_qp_metadata,
    parse_nos_units,
    extract_parts_from_nos,
    _clean,
)


# Simulated page text from a QP PDF (abbreviated)
MOCK_PAGES = [
    # Page 1 — title
    "Qualification Pack\nAutomotive Engine Repair Technician\nQP Code: ASC/Q1409\nVersion: 2.0\nNSQF Level: 4",
    # Page 2 — TOC (should be skipped by parser)
    "Qualification Pack\nContents\nASC/Q1409: Automotive Engine Repair Technician ......... 3\n"
    "ASC/N9801: Organize work and resources (Service) ......... 5\n"
    "ASC/N1418: Carry out service, repair and overhaul of vehicle engine ......... 15\n",
    # Page 3 — QP metadata
    (
        "Qualification Pack\nASC/Q1409: Automotive Engine Repair Technician\n"
        "Brief Job Description\n"
        "The individual is responsible for the service, maintenance, repair and overhaul "
        "of vehicle's engine and allied aggregates (like turbocharger).\n"
        "Personal Attributes\nGood communication.\n"
        "Applicable National Occupational Standards (NOS)\n"
        "Compulsory NOS:\n"
        "1. ASC/N9801: Organize work and resources (Service)\n"
        "2. ASC/N1418: Carry out service, repair and overhaul of vehicle engine\n"
        "Qualification Pack (QP) Parameters\n"
        "Sector Automotive\n"
        "Sub-Sector Automotive Vehicle Service\n"
        "Occupation Technical Service and Repair\n"
        "NSQF Level 4\n"
        "Country India\n"
    ),
    # Page 4 — NOS N9801 (generic, should still be parsed)
    (
        "ASC/N9801: Organize work and resources (Service)\n"
        "Description\n"
        "This NOS unit is about implementing safety and planning work.\n"
        "Scope\n"
        "The scope covers the following :\n"
        "Maintain safe working environment\n"
        "Perform work as per quality standards\n"
        "Elements and Performance Criteria\n"
        "To be competent, the user must be able to:\n"
        "PC1. organise work as per safety policies\n"
        "PC2. report breaches in safety procedures\n"
        "PC3. identify risks and hazards\n"
        "Knowledge and Understanding (KU)\n"
        "KU1. organisation procedures for health and safety\n"
        "KU2. emergency procedures for different situations\n"
        "Generic Skills (GS)\n"
        "GS1. read instructions and guidelines\n"
        "GS2. complete statutory documents\n"
    ),
    # Page 5 — NOS N1418 (domain-specific engine repair)
    (
        "ASC/N1418: Carry out service, repair and overhaul of vehicle engine and allied aggregates\n"
        "Description\n"
        "This NOS unit is about carrying out diagnosis of fault, service, repairs and "
        "overhaul of the engine and allied mechanical aggregates (like turbocharger).\n"
        "Scope\n"
        "The scope covers the following :\n"
        "Prepare for service of engine\n"
        "Perform service and overhaul\n"
        "Elements and Performance Criteria\n"
        "PC1. review the job card and understand work\n"
        "PC2. identify auto components related to engine aggregates\n"
        "PC3. diagnose faults in vehicle's engine and allied systems\n"
        "PC4. inspect components such as belts, timing chain, engine oil and filters\n"
        "PC5. perform repair of engine aggregates such as cylinder head, turbo charger, fuel pump\n"
        "PC6. refill coolants, engine oil and lubricants as per OEM guidelines\n"
        "Knowledge and Understanding (KU)\n"
        "KU1. different components and auto component manufacturer specifications\n"
        "KU2. basic technology of engine types (2/4 stroke, single/multi cylinder)\n"
        "KU3. functioning of clutch assembly, transmission system, steering system, brake system, suspension system\n"
        "KU4. typical symptoms of faults such as poor pickup, high engine oil consumption, low oil pressure\n"
        "KU5. the right materials for the job such as lubricants, seals, gaskets, fasteners\n"
        "Generic Skills (GS)\n"
        "GS1. read and interpret workshop documentation\n"
    ),
]


class TestClean:
    def test_removes_footer(self):
        text = "some content Deactivated-NSQC Approved || Automotive Skill Council of India 5"
        assert "NSQC" not in _clean(text)

    def test_normalizes_whitespace(self):
        assert _clean("  hello   world  ") == "hello world"


class TestParseQPMetadata:
    def test_extracts_job_description(self):
        meta = parse_qp_metadata(MOCK_PAGES)
        assert "service, maintenance, repair" in meta["job_description"]

    def test_extracts_sector(self):
        meta = parse_qp_metadata(MOCK_PAGES)
        assert meta["sector"] == "Automotive"

    def test_extracts_nsqf_level(self):
        meta = parse_qp_metadata(MOCK_PAGES)
        assert meta["nsqf_level"] == "4"

    def test_extracts_nos_codes(self):
        meta = parse_qp_metadata(MOCK_PAGES)
        assert "ASC/N9801" in meta["nos_codes"]
        assert "ASC/N1418" in meta["nos_codes"]


class TestParseNOSUnits:
    def test_parses_both_nos_units(self):
        units = parse_nos_units(MOCK_PAGES)
        codes = [u["nos_code"] for u in units]
        assert "ASC/N9801" in codes
        assert "ASC/N1418" in codes

    def test_engine_nos_has_domain_tasks(self):
        units = parse_nos_units(MOCK_PAGES)
        engine_nos = [u for u in units if u["nos_code"] == "ASC/N1418"][0]
        tasks = [pc["task"] for pc in engine_nos["performance_criteria"]]
        assert any("cylinder head" in t for t in tasks)
        assert any("timing chain" in t for t in tasks)

    def test_engine_nos_has_knowledge(self):
        units = parse_nos_units(MOCK_PAGES)
        engine_nos = [u for u in units if u["nos_code"] == "ASC/N1418"][0]
        assert len(engine_nos["knowledge"]) >= 3

    def test_nos_has_description(self):
        units = parse_nos_units(MOCK_PAGES)
        engine_nos = [u for u in units if u["nos_code"] == "ASC/N1418"][0]
        assert "turbocharger" in engine_nos["description"]

    def test_no_duplicate_nos(self):
        units = parse_nos_units(MOCK_PAGES)
        codes = [u["nos_code"] for u in units]
        assert len(codes) == len(set(codes))


class TestExtractParts:
    def test_extracts_engine_parts(self):
        nos = {
            "performance_criteria": [
                {"task": "inspect cylinder head and turbo charger"},
                {"task": "replace timing chain and fuel pump"},
                {"task": "refill coolant and engine oil"},
            ],
            "knowledge": [
                {"description": "clutch assembly and transmission system"},
                {"description": "brake system and suspension system"},
                {"description": "gasket and bearing types"},
            ],
        }
        parts = extract_parts_from_nos(nos)
        assert "cylinder head" in parts
        assert "turbo charger" in parts
        assert "timing chain" in parts
        assert "fuel pump" in parts
        assert "coolant" in parts
        assert "engine" in parts
        assert "clutch" in parts
        assert "brake" in parts
        assert "suspension" in parts
        assert "gasket" in parts
        assert "bearing" in parts
        assert "transmission" in parts

    def test_extracts_ev_parts(self):
        nos = {
            "performance_criteria": [
                {"task": "inspect EV battery and motor controller"},
                {"task": "check battery management system"},
            ],
            "knowledge": [
                {"description": "regenerative braking and inverter"},
            ],
        }
        parts = extract_parts_from_nos(nos)
        assert "battery management" in parts
        assert "inverter" in parts


class TestOutputFile:
    """Test the actual output file if it exists (integration check)."""

    @pytest.fixture
    def output_data(self):
        output_path = Path(__file__).parent.parent / "data" / "knowledge_graph" / "asdc_tasks.json"
        if not output_path.exists():
            pytest.skip("Output file not generated yet")
        with open(output_path) as f:
            return json.load(f)

    def test_has_10_plus_qps(self, output_data):
        assert output_data["metadata"]["total_qualification_packs"] >= 10

    def test_has_task_mappings(self, output_data):
        assert output_data["metadata"]["total_tasks"] > 100

    def test_has_knowledge_mappings(self, output_data):
        assert output_data["metadata"]["total_knowledge"] > 100

    def test_each_qp_has_nos(self, output_data):
        for qp in output_data["qualification_packs"]:
            assert len(qp["nos_units"]) >= 2, f"{qp['qp_code']} has too few NOS units"

    def test_each_qp_has_parts(self, output_data):
        qps_with_parts = [qp for qp in output_data["qualification_packs"] if qp["all_parts_mentioned"]]
        assert len(qps_with_parts) >= 10
