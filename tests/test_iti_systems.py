"""Tests for ITI syllabus vehicle system → parts extraction."""
import json
from pathlib import Path

import pytest
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from scrapers.iti_systems_parser import VEHICLE_SYSTEMS, extract_systems


class TestVehicleSystems:
    """Tests for the structured system definitions."""

    def test_minimum_8_systems(self):
        """Must define at least 8 vehicle systems."""
        assert len(VEHICLE_SYSTEMS) >= 8

    def test_each_system_has_5_plus_parts(self):
        """Every system must have at least 5 component parts."""
        for system in VEHICLE_SYSTEMS:
            assert len(system["parts"]) >= 5, (
                f"{system['system_name']} has only {len(system['parts'])} parts"
            )

    def test_system_ids_are_unique(self):
        ids = [s["system_id"] for s in VEHICLE_SYSTEMS]
        assert len(ids) == len(set(ids))

    def test_system_id_format(self):
        for s in VEHICLE_SYSTEMS:
            assert s["system_id"].startswith("system:"), f"Bad ID: {s['system_id']}"

    def test_required_fields(self):
        for s in VEHICLE_SYSTEMS:
            assert s["system_name"]
            assert s["system_id"]
            assert s["description"]
            assert s["source_trade"]
            assert s["vehicle_types"]

    def test_parts_have_required_fields(self):
        for s in VEHICLE_SYSTEMS:
            for part in s["parts"]:
                assert "name" in part, f"Missing name in {s['system_name']}"
                assert "aliases" in part, f"Missing aliases for {part['name']}"
                assert "role" in part, f"Missing role for {part['name']}"
                assert isinstance(part["aliases"], list)

    def test_no_duplicate_parts_within_system(self):
        for s in VEHICLE_SYSTEMS:
            names = [p["name"].lower() for p in s["parts"]]
            assert len(names) == len(set(names)), (
                f"Duplicate parts in {s['system_name']}"
            )


class TestExtractSystems:
    """Tests for the extract_systems() function."""

    @pytest.fixture
    def result(self, tmp_path):
        """Run extraction with empty PDF dir."""
        return extract_systems(pdf_dir=tmp_path)

    def test_output_has_metadata(self, result):
        assert "metadata" in result
        assert "systems" in result
        assert result["metadata"]["total_systems"] >= 8

    def test_output_has_total_parts(self, result):
        assert result["metadata"]["total_parts"] >= 40

    def test_systems_structure(self, result):
        for s in result["systems"]:
            assert "system_name" in s
            assert "system_id" in s
            assert "description" in s
            assert "parts" in s
            assert "source_trade" in s
            assert "vehicle_types" in s

    def test_key_systems_present(self, result):
        """Core vehicle systems must be present."""
        system_ids = {s["system_id"] for s in result["systems"]}
        required = [
            "system:engine",
            "system:fuel_system",
            "system:cooling_system",
            "system:braking_system",
            "system:suspension",
            "system:steering",
            "system:transmission",
            "system:electrical_system",
        ]
        for sys_id in required:
            assert sys_id in system_ids, f"Missing required system: {sys_id}"

    def test_json_serializable(self, result):
        """Output must be valid JSON."""
        json.dumps(result, ensure_ascii=False)
