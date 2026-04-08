"""Shopify products.json scraper for Indian auto parts platforms."""
import json
import re
import sys
import time
import logging
from html import unescape
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import Product
from auto_parts_search.config import (
    SHOPIFY_TARGETS,
    REQUEST_DELAY,
    MAX_PAGES,
    USER_AGENT,
    RAW_DIR,
)

logger = logging.getLogger(__name__)

# Known vehicle makes and models for tag extraction
VEHICLE_MAKES = {
    "maruti", "hyundai", "tata", "mahindra", "kia", "toyota", "honda",
    "ford", "volkswagen", "skoda", "renault", "nissan", "mg", "jeep",
    "hero", "bajaj", "tvs", "royal enfield", "yamaha", "suzuki",
    "kawasaki", "ktm", "aprilia", "piaggio", "ola", "ather",
}

VEHICLE_MODELS = {
    # 4W
    "swift", "baleno", "alto", "dzire", "brezza", "ertiga", "wagon r",
    "creta", "venue", "i20", "i10", "verna", "tucson", "nexon", "punch",
    "harrier", "safari", "thar", "xuv700", "xuv300", "bolero", "scorpio",
    "seltos", "sonet", "carens", "fortuner", "innova", "city", "amaze",
    "ecosport", "polo", "vento", "rapid", "octavia", "kwid", "triber",
    "magnite", "kicks", "hector", "astor", "compass",
    # 2W
    "activa", "splendor", "pulsar", "apache", "jupiter", "ntorq",
    "classic 350", "bullet", "himalayan", "meteor", "fz", "r15", "mt15",
    "duke", "rc", "dominar", "avenger", "platina", "ct100", "shine",
    "unicorn", "hornet", "cb350", "xpulse", "access", "burgman",
}

HTML_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(html: str) -> str:
    """Remove HTML tags and decode entities."""
    if not html:
        return ""
    text = HTML_TAG_RE.sub(" ", html)
    text = unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_vehicle_info(tags: list[str]) -> dict:
    """Extract vehicle make and model from Shopify product tags."""
    tags_lower = [t.strip().lower() for t in tags]
    result = {"make": "", "model": "", "year": ""}

    for tag in tags_lower:
        # Check makes
        for make in VEHICLE_MAKES:
            if make in tag:
                result["make"] = make.title()
                break
        # Check models
        for model in VEHICLE_MODELS:
            if model in tag:
                result["model"] = model.title()
                break
        # Check year (4-digit number between 1990-2030)
        year_match = re.search(r"\b(19\d{2}|20[0-3]\d)\b", tag)
        if year_match:
            result["year"] = year_match.group(1)

    return result


class ShopifyScraper:
    """Scrapes products from a Shopify store's public products.json endpoint."""

    def __init__(self, name: str, base_url: str, vehicle_types: list[str]):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.vehicle_types = vehicle_types
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def scrape(self, max_pages: int = MAX_PAGES) -> list[Product]:
        """Fetch all products from the store, paginating through products.json."""
        all_products: list[Product] = []
        page = 1

        while page <= max_pages:
            url = f"{self.base_url}/products.json"
            params = {"page": page, "limit": 250}

            try:
                resp = self._request_with_retry(url, params)
                data = resp.json()
            except Exception as e:
                logger.error(f"[{self.name}] Failed on page {page}: {e}")
                break

            products = data.get("products", [])
            if not products:
                logger.info(f"[{self.name}] No more products at page {page}.")
                break

            for raw in products:
                try:
                    product = self._normalize_product(raw)
                    all_products.append(product)
                except Exception as e:
                    pid = raw.get("id", "unknown")
                    logger.warning(f"[{self.name}] Skipping product {pid}: {e}")

            logger.info(f"[{self.name}] Page {page}: {len(products)} products (total: {len(all_products)})")
            page += 1

            if page <= max_pages:
                time.sleep(REQUEST_DELAY)

        return all_products

    def _request_with_retry(
        self, url: str, params: dict, max_retries: int = 3
    ) -> requests.Response:
        """Make a GET request with exponential backoff on 429 / timeouts."""
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code == 429:
                    wait = REQUEST_DELAY * (2 ** attempt)
                    logger.warning(f"[{self.name}] Rate limited. Waiting {wait}s...")
                    time.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.Timeout:
                wait = REQUEST_DELAY * (2 ** attempt)
                logger.warning(f"[{self.name}] Timeout on attempt {attempt + 1}. Waiting {wait}s...")
                time.sleep(wait)
        raise RuntimeError(f"[{self.name}] Failed after {max_retries} retries: {url}")

    def _normalize_product(self, raw: dict) -> Product:
        """Convert a Shopify product JSON object to our Product dataclass."""
        tags = raw.get("tags", [])
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(",")]

        vehicle_info = extract_vehicle_info(tags)

        # Price from first variant
        variants = raw.get("variants", [])
        price = 0.0
        if variants:
            price_str = variants[0].get("price", "0")
            try:
                price = float(price_str)
            except (ValueError, TypeError):
                price = 0.0

        handle = raw.get("handle", "")
        product_url = f"{self.base_url}/products/{handle}" if handle else ""

        vehicle_type = ", ".join(self.vehicle_types) if self.vehicle_types else ""

        return Product(
            source=self.name,
            product_id=str(raw.get("id", "")),
            name=raw.get("title", ""),
            category=raw.get("product_type", ""),
            subcategory="",
            brand=raw.get("vendor", ""),
            part_number="",
            vehicle_make=vehicle_info["make"],
            vehicle_model=vehicle_info["model"],
            vehicle_year=vehicle_info["year"],
            vehicle_variant="",
            vehicle_type=vehicle_type,
            price=price,
            description=strip_html(raw.get("body_html", "")),
            url=product_url,
        )


def scrape_all_shopify() -> list[Product]:
    """Scrape all configured Shopify targets and return combined product list."""
    all_products: list[Product] = []

    for name, cfg in SHOPIFY_TARGETS.items():
        logger.info(f"Scraping {name}...")
        scraper = ShopifyScraper(
            name=name,
            base_url=cfg["base_url"],
            vehicle_types=cfg["vehicle_types"],
        )
        products = scraper.scrape()
        all_products.extend(products)
        logger.info(f"{name}: {len(products)} products scraped.")

    logger.info(f"Total: {len(all_products)} products from {len(SHOPIFY_TARGETS)} stores.")
    return all_products


def save_products(products: list[Product], output_path: str | Path) -> None:
    """Write products to a JSONL file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for p in products:
            f.write(json.dumps(p.to_dict(), ensure_ascii=False) + "\n")

    logger.info(f"Saved {len(products)} products to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_file = RAW_DIR / "shopify_products.jsonl"
    products = scrape_all_shopify()
    save_products(products, output_file)
    print(f"Done. {len(products)} products saved to {output_file}")
