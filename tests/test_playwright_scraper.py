"""Tests for Playwright scrapers — no real browser needed."""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import Product
from scrapers.playwright_scraper import (
    BoodmoScraper,
    AutozillaScraper,
    PlaywrightScraper,
    save_products,
    scrape_all_playwright,
    _build_scrapers,
)


def run_async(coro):
    """Helper to run async tests without pytest-asyncio."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


def test_playwright_scraper_init():
    s = PlaywrightScraper("test", "https://example.com", ["4W"])
    assert s.name == "test"
    assert s.base_url == "https://example.com"
    assert s.vehicle_types == ["4W"]
    assert s.browser is None
    assert s.page is None


def test_boodmo_scraper_init():
    s = BoodmoScraper(name="boodmo", base_url="https://boodmo.com", vehicle_types=["4W", "2W"])
    assert s.name == "boodmo"
    assert "boodmo.com" in s.base_url
    assert s.vehicle_types == ["4W", "2W"]


def test_autozilla_scraper_init():
    s = AutozillaScraper(name="autozilla", base_url="https://www.autozilla.co", vehicle_types=["4W"])
    assert s.name == "autozilla"
    assert "autozilla" in s.base_url


def test_base_url_trailing_slash_stripped():
    s = BoodmoScraper(name="test", base_url="https://example.com/", vehicle_types=[])
    assert s.base_url == "https://example.com"


def test_base_scraper_scrape_raises():
    s = PlaywrightScraper(name="base", base_url="https://example.com", vehicle_types=[])
    with pytest.raises(NotImplementedError):
        run_async(s.scrape())


def test_build_scrapers_from_config():
    scrapers = _build_scrapers()
    names = {s.name for s in scrapers}
    assert "boodmo" in names
    assert "autozilla" in names
    assert len(scrapers) == 2


# ---------------------------------------------------------------------------
# Product normalization / parsing tests
# ---------------------------------------------------------------------------


def test_parse_price_inr():
    assert BoodmoScraper._parse_price("₹1,234.50") == 1234.50


def test_parse_price_rs():
    assert BoodmoScraper._parse_price("Rs. 999") == 999.0


def test_parse_price_empty():
    assert BoodmoScraper._parse_price("") == 0.0


def test_parse_price_garbage():
    assert BoodmoScraper._parse_price("N/A") == 0.0


def test_parse_price_plain_number():
    assert BoodmoScraper._parse_price("2500") == 2500.0


def test_extract_id_from_url():
    assert BoodmoScraper._extract_id_from_url("https://boodmo.com/part/12345") == "12345"


def test_extract_id_from_url_trailing_slash():
    assert BoodmoScraper._extract_id_from_url("https://boodmo.com/part/12345/") == "12345"


def test_extract_id_empty_url():
    assert BoodmoScraper._extract_id_from_url("") == ""


def test_parse_vehicle_maruti():
    make, model = BoodmoScraper._parse_vehicle_from_name("Brake Pad for Maruti Swift")
    assert make == "Maruti"
    assert model == "Swift"


def test_parse_vehicle_hyundai():
    make, model = BoodmoScraper._parse_vehicle_from_name("Hyundai Creta Front Bumper")
    assert make == "Hyundai"
    assert model == "Creta"


def test_parse_vehicle_maruti_suzuki():
    make, model = BoodmoScraper._parse_vehicle_from_name("Clutch Plate Maruti Suzuki Alto")
    assert make == "Maruti Suzuki"
    assert model == "Alto"


def test_parse_vehicle_none_found():
    make, model = BoodmoScraper._parse_vehicle_from_name("Generic Brake Fluid 500ml")
    assert make == ""
    assert model == ""


def test_parse_vehicle_for_keyword_skipped():
    make, model = BoodmoScraper._parse_vehicle_from_name("Honda for something")
    assert make == "Honda"
    assert model == ""


def test_make_product_sets_source():
    s = BoodmoScraper(name="boodmo", base_url="https://boodmo.com", vehicle_types=["4W"])
    p = s._make_product(product_id="123", name="Test Part")
    assert p.source == "boodmo"
    assert p.product_id == "123"
    assert p.name == "Test Part"


def test_product_schema_round_trip():
    p = Product(
        source="boodmo",
        product_id="12345",
        name="Brake Pad Front",
        category="Brake System",
        brand="Bosch",
        vehicle_make="Maruti",
        vehicle_model="Swift",
        vehicle_year="2019",
        vehicle_type="4W",
        price=1200.0,
    )
    d = p.to_dict()
    assert d["source"] == "boodmo"
    p2 = Product(**d)
    assert p2.name == p.name


# ---------------------------------------------------------------------------
# save_products tests
# ---------------------------------------------------------------------------


def test_save_products_jsonl(tmp_path):
    products = [
        Product(source="test", product_id="1", name="Brake Pad", price=500.0),
        Product(source="test", product_id="2", name="Oil Filter", brand="Bosch"),
    ]
    out = tmp_path / "output.jsonl"
    save_products(products, out)

    lines = out.read_text().strip().split("\n")
    assert len(lines) == 2

    p1 = json.loads(lines[0])
    assert p1["name"] == "Brake Pad"
    assert p1["price"] == 500.0

    p2 = json.loads(lines[1])
    assert p2["brand"] == "Bosch"


def test_save_products_creates_parent_dirs(tmp_path):
    out = tmp_path / "deep" / "nested" / "output.jsonl"
    save_products([], out)
    assert out.exists()


def test_save_empty_list(tmp_path):
    out = tmp_path / "empty.jsonl"
    save_products([], out)
    assert out.read_text() == ""


# ---------------------------------------------------------------------------
# Mock-based scraper tests (no real browser)
# ---------------------------------------------------------------------------


def test_boodmo_scrape_handles_browser_failure():
    """Scraper returns empty list if browser launch fails."""
    async def _run():
        s = BoodmoScraper(name="boodmo", base_url="https://boodmo.com", vehicle_types=["4W"])
        with patch.object(s, "_launch_browser", side_effect=Exception("No browser")):
            return await s.scrape(max_pages=1)

    products = run_async(_run())
    assert products == []


def test_boodmo_scrape_returns_products_from_categories():
    """Scraper delegates to category scraping."""
    async def _run():
        s = BoodmoScraper(name="boodmo", base_url="https://boodmo.com", vehicle_types=["4W"])
        fake_product = Product(source="boodmo", product_id="1", name="Test")
        with (
            patch.object(s, "_launch_browser", new_callable=AsyncMock),
            patch.object(s, "_close_browser", new_callable=AsyncMock),
            patch.object(
                s, "_get_categories", new_callable=AsyncMock,
                return_value=[("Brakes", "https://boodmo.com/catalog/brakes/")],
            ),
            patch.object(
                s, "_scrape_category", new_callable=AsyncMock,
                return_value=([fake_product], 1),
            ),
        ):
            return await s.scrape(max_pages=5)

    products = run_async(_run())
    assert len(products) == 1
    assert products[0].name == "Test"


def test_autozilla_scrape_handles_browser_failure():
    async def _run():
        s = AutozillaScraper(
            name="autozilla", base_url="https://www.autozilla.co", vehicle_types=["4W"],
        )
        with patch.object(s, "_launch_browser", side_effect=Exception("No browser")):
            return await s.scrape(max_pages=1)

    products = run_async(_run())
    assert products == []


def test_autozilla_scrape_delegates_to_categories():
    async def _run():
        s = AutozillaScraper(
            name="autozilla", base_url="https://www.autozilla.co", vehicle_types=["4W"],
        )
        fake_product = Product(source="autozilla", product_id="2", name="Oil Filter")
        with (
            patch.object(s, "_launch_browser", new_callable=AsyncMock),
            patch.object(s, "_close_browser", new_callable=AsyncMock),
            patch.object(
                s, "_get_categories", new_callable=AsyncMock,
                return_value=[("Filters", "https://www.autozilla.co/filters")],
            ),
            patch.object(
                s, "_scrape_category", new_callable=AsyncMock,
                return_value=([fake_product], 1),
            ),
        ):
            return await s.scrape(max_pages=5)

    products = run_async(_run())
    assert len(products) == 1
    assert products[0].name == "Oil Filter"


def test_scrape_all_combines_results():
    async def _run():
        p1 = Product(source="boodmo", product_id="1", name="Part A")
        p2 = Product(source="autozilla", product_id="2", name="Part B")

        async def mock_boodmo_scrape(max_pages=50):
            return [p1]

        async def mock_autozilla_scrape(max_pages=50):
            return [p2]

        with patch("scrapers.playwright_scraper._build_scrapers") as mock_build:
            mock_boodmo = MagicMock(spec=BoodmoScraper)
            mock_boodmo.name = "boodmo"
            mock_boodmo.scrape = mock_boodmo_scrape

            mock_autozilla = MagicMock(spec=AutozillaScraper)
            mock_autozilla.name = "autozilla"
            mock_autozilla.scrape = mock_autozilla_scrape

            mock_build.return_value = [mock_boodmo, mock_autozilla]
            return await scrape_all_playwright(max_pages=5)

    products = run_async(_run())
    assert len(products) == 2
    sources = {p.source for p in products}
    assert sources == {"boodmo", "autozilla"}
