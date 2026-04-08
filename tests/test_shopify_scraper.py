"""Tests for Shopify scraper — no real HTTP requests."""
import json
from unittest.mock import patch, MagicMock

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scrapers.shopify_scraper import (
    ShopifyScraper,
    strip_html,
    extract_vehicle_info,
    save_products,
    scrape_all_shopify,
)
from auto_parts_search.schemas import Product


MOCK_SHOPIFY_PRODUCT = {
    "id": 123456,
    "title": "Brake Pad Set - Front",
    "body_html": "<p>High quality <b>ceramic</b> brake pads for Maruti Swift.</p>",
    "vendor": "Brembo",
    "product_type": "Brake Parts",
    "handle": "brake-pad-set-front",
    "tags": ["Maruti", "Swift", "2019", "Brake", "Front"],
    "variants": [
        {"id": 1, "price": "1499.00", "title": "Default"},
    ],
    "images": [
        {"src": "https://cdn.shopify.com/img1.jpg"},
    ],
}

MOCK_SHOPIFY_PRODUCT_TAGS_STRING = {
    "id": 789,
    "title": "Chain Sprocket Kit",
    "body_html": "",
    "vendor": "RK",
    "product_type": "Drive",
    "handle": "chain-sprocket-kit",
    "tags": "Hero, Splendor, Chain, Sprocket",
    "variants": [{"id": 2, "price": "850"}],
    "images": [],
}

MOCK_SHOPIFY_PRODUCT_NO_VEHICLE = {
    "id": 999,
    "title": "Universal Engine Oil 10W30",
    "body_html": "<div>Suitable for all &amp; any bike</div>",
    "vendor": "Motul",
    "product_type": "Lubricants",
    "handle": "universal-engine-oil",
    "tags": ["Oil", "10W30", "Synthetic"],
    "variants": [],
    "images": [],
}


@pytest.fixture
def scraper():
    return ShopifyScraper(name="test_store", base_url="https://example.com", vehicle_types=["4W"])


class TestStripHtml:
    def test_removes_tags(self):
        assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_decodes_entities(self):
        assert strip_html("Oil &amp; Filter") == "Oil & Filter"

    def test_collapses_whitespace(self):
        assert strip_html("<p>  too   many   spaces  </p>") == "too many spaces"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_none_input(self):
        assert strip_html(None) == ""


class TestExtractVehicleInfo:
    def test_make_and_model(self):
        tags = ["Maruti", "Swift", "Front Brake"]
        info = extract_vehicle_info(tags)
        assert info["make"] == "Maruti"
        assert info["model"] == "Swift"

    def test_year_extraction(self):
        tags = ["2019", "Hyundai", "Creta"]
        info = extract_vehicle_info(tags)
        assert info["year"] == "2019"
        assert info["make"] == "Hyundai"
        assert info["model"] == "Creta"

    def test_two_wheeler_brands(self):
        tags = ["Hero", "Splendor Plus"]
        info = extract_vehicle_info(tags)
        assert info["make"] == "Hero"
        assert info["model"] == "Splendor"

    def test_no_vehicle_info(self):
        tags = ["Oil", "10W30", "Synthetic"]
        info = extract_vehicle_info(tags)
        assert info["make"] == ""
        assert info["model"] == ""
        assert info["year"] == ""

    def test_case_insensitive(self):
        tags = ["HONDA", "activa"]
        info = extract_vehicle_info(tags)
        assert info["make"] == "Honda"
        assert info["model"] == "Activa"


class TestNormalizeProduct:
    def test_full_product(self, scraper):
        product = scraper._normalize_product(MOCK_SHOPIFY_PRODUCT)
        assert isinstance(product, Product)
        assert product.source == "test_store"
        assert product.product_id == "123456"
        assert product.name == "Brake Pad Set - Front"
        assert product.brand == "Brembo"
        assert product.category == "Brake Parts"
        assert product.vehicle_make == "Maruti"
        assert product.vehicle_model == "Swift"
        assert product.vehicle_year == "2019"
        assert product.price == 1499.00
        assert product.url == "https://example.com/products/brake-pad-set-front"
        assert "<p>" not in product.description
        assert "ceramic" in product.description

    def test_tags_as_string(self, scraper):
        product = scraper._normalize_product(MOCK_SHOPIFY_PRODUCT_TAGS_STRING)
        assert product.vehicle_make == "Hero"
        assert product.vehicle_model == "Splendor"
        assert product.brand == "RK"

    def test_no_variants_zero_price(self, scraper):
        product = scraper._normalize_product(MOCK_SHOPIFY_PRODUCT_NO_VEHICLE)
        assert product.price == 0.0
        assert product.vehicle_make == ""
        assert product.vehicle_model == ""

    def test_html_stripped_from_description(self, scraper):
        product = scraper._normalize_product(MOCK_SHOPIFY_PRODUCT_NO_VEHICLE)
        assert "<div>" not in product.description
        assert "& any bike" in product.description  # decoded entity

    def test_vehicle_type_from_scraper(self, scraper):
        product = scraper._normalize_product(MOCK_SHOPIFY_PRODUCT)
        assert product.vehicle_type == "4W"


class TestScrape:
    @patch("scrapers.shopify_scraper.time.sleep")
    def test_scrape_paginates_and_stops(self, mock_sleep, scraper):
        page1_resp = MagicMock()
        page1_resp.status_code = 200
        page1_resp.json.return_value = {"products": [MOCK_SHOPIFY_PRODUCT]}

        page2_resp = MagicMock()
        page2_resp.status_code = 200
        page2_resp.json.return_value = {"products": []}

        with patch.object(scraper, "_request_with_retry", side_effect=[page1_resp, page2_resp]):
            products = scraper.scrape(max_pages=5)

        assert len(products) == 1
        assert products[0].name == "Brake Pad Set - Front"

    @patch("scrapers.shopify_scraper.time.sleep")
    def test_scrape_respects_max_pages(self, mock_sleep, scraper):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"products": [MOCK_SHOPIFY_PRODUCT]}

        with patch.object(scraper, "_request_with_retry", return_value=resp):
            products = scraper.scrape(max_pages=2)

        assert len(products) == 2  # 1 product per page * 2 pages


class TestSaveProducts:
    def test_writes_jsonl(self, tmp_path):
        products = [
            Product(source="test", product_id="1", name="Part A"),
            Product(source="test", product_id="2", name="Part B"),
        ]
        out = tmp_path / "out.jsonl"
        save_products(products, out)

        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        parsed = json.loads(lines[0])
        assert parsed["name"] == "Part A"
        assert parsed["source"] == "test"
