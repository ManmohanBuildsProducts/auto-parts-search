"""Tests for NHTSA recalls scraper — no real HTTP requests."""
import json
from unittest.mock import patch, MagicMock

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.nhtsa_scraper import (
    fetch_recalls,
    parse_component,
    scrape_nhtsa_recalls,
    save_recalls,
    INDIAN_RELEVANT_VEHICLES,
)


MOCK_RECALL = {
    "Manufacturer": "Honda (American Honda Motor Co.)",
    "NHTSACampaignNumber": "21V215000",
    "parkIt": False,
    "parkOutSide": False,
    "ReportReceivedDate": "25/03/2021",
    "Component": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
    "Summary": "Honda is recalling certain 2019-2020 vehicles. The low-pressure fuel pump may fail.",
    "Consequence": "Fuel pump failure can cause an engine stall.",
    "Remedy": "Dealers will replace the fuel pump assembly.",
    "Notes": "",
    "ModelYear": "2020",
    "Make": "HONDA",
    "Model": "CR-V",
}

MOCK_RECALL_2 = {
    "Manufacturer": "Hyundai Motor America",
    "NHTSACampaignNumber": "22V100000",
    "parkIt": False,
    "parkOutSide": False,
    "ReportReceivedDate": "10/01/2022",
    "Component": "SERVICE BRAKES, HYDRAULIC:FOUNDATION COMPONENTS:MASTER CYLINDER",
    "Summary": "Hyundai is recalling certain vehicles due to brake issues.",
    "Consequence": "Brake master cylinder may fail.",
    "Remedy": "Dealers will inspect and repair.",
    "Notes": "",
    "ModelYear": "2022",
    "Make": "HYUNDAI",
    "Model": "TUCSON",
}


class TestParseComponent:
    def test_three_level(self):
        result = parse_component("FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP")
        assert result["system"] == "FUEL SYSTEM, GASOLINE"
        assert result["subsystem"] == "DELIVERY"
        assert result["component"] == "FUEL PUMP"
        assert result["raw"] == "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP"

    def test_two_level(self):
        result = parse_component("ELECTRICAL SYSTEM:SOFTWARE")
        assert result["system"] == "ELECTRICAL SYSTEM"
        assert result["subsystem"] == "SOFTWARE"
        assert "component" not in result

    def test_one_level(self):
        result = parse_component("AIR BAGS")
        assert result["system"] == "AIR BAGS"
        assert "subsystem" not in result

    def test_four_level(self):
        result = parse_component("STRUCTURE:BODY:ROOF AND PILLARS:SUNROOF")
        assert result["system"] == "STRUCTURE"
        assert result["subsystem"] == "BODY"
        assert result["component"] == "ROOF AND PILLARS"
        assert result["detail"] == "SUNROOF"


class TestFetchRecalls:
    def test_successful_fetch(self):
        session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Count": 1, "results": [MOCK_RECALL]}
        session.get.return_value = mock_resp

        results = fetch_recalls(session, "HONDA", "CR-V", 2020)
        assert len(results) == 1
        assert results[0]["Component"] == "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP"

        session.get.assert_called_once()
        call_args = session.get.call_args
        assert call_args[1]["params"]["make"] == "HONDA"
        assert call_args[1]["params"]["model"] == "CR-V"

    def test_empty_results(self):
        session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"Count": 0, "results": []}
        session.get.return_value = mock_resp

        results = fetch_recalls(session, "SUZUKI", "SWIFT", 2020)
        assert results == []

    def test_network_error(self):
        import requests as req
        session = MagicMock()
        session.get.side_effect = req.ConnectionError("Connection refused")

        results = fetch_recalls(session, "HONDA", "CIVIC", 2020)
        assert results == []


class TestIndianRelevantVehicles:
    def test_expected_makes(self):
        expected = {"SUZUKI", "HYUNDAI", "HONDA", "TOYOTA", "KIA", "NISSAN"}
        assert set(INDIAN_RELEVANT_VEHICLES.keys()) == expected

    def test_no_tata_mahindra(self):
        assert "TATA" not in INDIAN_RELEVANT_VEHICLES
        assert "MAHINDRA" not in INDIAN_RELEVANT_VEHICLES

    def test_models_are_nonempty(self):
        for make, models in INDIAN_RELEVANT_VEHICLES.items():
            assert len(models) > 0, f"{make} has no models"


class TestSaveRecalls:
    def test_writes_json(self, tmp_path):
        data = {
            "recalls": [
                {
                    "campaign_number": "21V215000",
                    "make": "HONDA",
                    "model": "CR-V",
                    "model_year": "2020",
                    "component_raw": "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP",
                    "component_parsed": {"system": "FUEL SYSTEM, GASOLINE"},
                    "summary": "Test",
                    "consequence": "Test",
                    "remedy": "Test",
                    "report_date": "25/03/2021",
                    "manufacturer": "Honda",
                }
            ],
            "component_vehicle_map": {
                "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP": ["HONDA|CR-V|2020"]
            },
            "component_crossref": {
                "FUEL PUMP": ["HONDA|CR-V"]
            },
            "stats": {
                "total_queries": 1,
                "empty_queries": 0,
                "total_recalls": 1,
                "unique_campaigns": 1,
                "unique_components": 1,
                "unique_component_names": 1,
                "makes_queried": ["HONDA"],
            },
        }
        out = tmp_path / "nhtsa_recalls.json"
        save_recalls(data, out)

        loaded = json.loads(out.read_text())
        assert loaded["metadata"]["source"] == "https://api.nhtsa.gov/recalls/recallsByVehicle"
        assert len(loaded["recalls"]) == 1
        assert "FUEL PUMP" in loaded["component_crossref"]
        assert loaded["stats"]["total_recalls"] == 1
