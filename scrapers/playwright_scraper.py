"""Playwright-based scrapers for JS-heavy Indian auto parts platforms."""

import asyncio
import json
import logging
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, TimeoutError as PlaywrightTimeout

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import Product
from auto_parts_search.config import (
    PLAYWRIGHT_TARGETS,
    REQUEST_DELAY,
    MAX_PAGES,
    RAW_DIR,
)

logger = logging.getLogger(__name__)


class PlaywrightScraper:
    """Base scraper for JS-rendered auto parts platforms."""

    def __init__(self, name: str, base_url: str, vehicle_types: list[str]):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.vehicle_types = vehicle_types
        self.browser: Browser | None = None
        self.page: Page | None = None
        self._pw = None
        self._delay = REQUEST_DELAY

    async def _launch_browser(self) -> None:
        """Launch headless Chromium."""
        self._pw = await async_playwright().start()
        self.browser = await self._pw.chromium.launch(headless=True)
        context = await self.browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        self.page = await context.new_page()

    async def _close_browser(self) -> None:
        """Close browser and Playwright."""
        if self.browser:
            await self.browser.close()
        if self._pw:
            await self._pw.stop()
        self.browser = None
        self.page = None

    async def _navigate(self, url: str, wait_until: str = "networkidle") -> bool:
        """Navigate to URL with rate limiting and error handling.

        Returns True on success, False on failure.
        """
        await asyncio.sleep(self._delay)
        try:
            await self.page.goto(url, wait_until=wait_until, timeout=30000)
            return True
        except PlaywrightTimeout:
            logger.warning("Timeout loading %s", url)
            return False
        except Exception as e:
            logger.error("Failed to load %s: %s", url, e)
            return False

    async def _screenshot_on_error(self, context: str) -> None:
        """Save a screenshot for debugging when something goes wrong."""
        if not self.page:
            return
        try:
            screenshot_dir = RAW_DIR / "screenshots"
            screenshot_dir.mkdir(parents=True, exist_ok=True)
            path = screenshot_dir / f"{self.name}_{context}.png"
            await self.page.screenshot(path=str(path), full_page=True)
            logger.info("Screenshot saved: %s", path)
        except Exception as e:
            logger.debug("Could not save screenshot: %s", e)

    async def scrape(self, max_pages: int = MAX_PAGES) -> list[Product]:
        """Scrape products. Subclasses must implement this."""
        raise NotImplementedError

    def _make_product(self, **kwargs) -> Product:
        """Create a Product with source pre-filled."""
        return Product(source=self.name, **kwargs)


# ---------------------------------------------------------------------------
# Boodmo (Angular SPA)
# ---------------------------------------------------------------------------


class BoodmoScraper(PlaywrightScraper):
    """Scraper for boodmo.com — Angular SPA, ~13M SKUs.

    Strategy:
    1. Hit /catalog/ to discover top-level categories.
    2. For each category, navigate listing pages.
    3. Extract product cards from the listing grid.
    4. Optionally visit product detail for vehicle compatibility.
    """

    CATALOG_URL = "/catalog/"

    async def scrape(self, max_pages: int = MAX_PAGES) -> list[Product]:
        products: list[Product] = []
        try:
            await self._launch_browser()
            categories = await self._get_categories()
            logger.info("[boodmo] Found %d categories", len(categories))

            pages_scraped = 0
            for cat_name, cat_url in categories:
                if pages_scraped >= max_pages:
                    break
                page_products, pages_used = await self._scrape_category(
                    cat_name, cat_url, max_pages - pages_scraped
                )
                products.extend(page_products)
                pages_scraped += pages_used
        except Exception as e:
            logger.error("[boodmo] Scrape failed: %s", e)
            await self._screenshot_on_error("scrape_error")
        finally:
            await self._close_browser()

        logger.info("[boodmo] Total products scraped: %d", len(products))
        return products

    async def _get_categories(self) -> list[tuple[str, str]]:
        """Get category names and URLs from the catalog page."""
        url = f"{self.base_url}{self.CATALOG_URL}"
        if not await self._navigate(url):
            await self._screenshot_on_error("catalog_load")
            return []

        # Wait for Angular to render category links
        try:
            await self.page.wait_for_selector(
                "a[href*='/catalog/']", timeout=10000
            )
        except PlaywrightTimeout:
            logger.warning("[boodmo] No category links found on catalog page")
            await self._screenshot_on_error("no_categories")
            return []

        links = await self.page.query_selector_all("a[href*='/catalog/']")
        categories: list[tuple[str, str]] = []
        seen_urls: set[str] = set()
        for link in links:
            href = await link.get_attribute("href") or ""
            text = (await link.inner_text()).strip()
            # Skip the top-level /catalog/ link itself and duplicates
            if href and href != "/catalog/" and href not in seen_urls and text:
                full_url = href if href.startswith("http") else f"{self.base_url}{href}"
                categories.append((text, full_url))
                seen_urls.add(href)

        return categories

    async def _scrape_category(
        self, cat_name: str, cat_url: str, remaining_pages: int
    ) -> tuple[list[Product], int]:
        """Scrape product listings from a category. Returns (products, pages_used)."""
        products: list[Product] = []
        pages_used = 0

        if not await self._navigate(cat_url):
            return products, 0

        pages_used += 1

        # Extract product cards from current page
        page_products = await self._extract_product_cards(cat_name)
        products.extend(page_products)

        # Paginate
        while pages_used < remaining_pages:
            next_btn = await self.page.query_selector(
                "a.pagination-next, a[rel='next'], .next-page a, "
                "[class*='pagination'] a:has-text('Next'), "
                "[class*='pagination'] a:has-text('>')"
            )
            if not next_btn:
                break

            try:
                await next_btn.click()
                await self.page.wait_for_load_state("networkidle", timeout=15000)
                pages_used += 1
                page_products = await self._extract_product_cards(cat_name)
                products.extend(page_products)
                await asyncio.sleep(self._delay)
            except Exception as e:
                logger.warning("[boodmo] Pagination failed in %s: %s", cat_name, e)
                break

        return products, pages_used

    async def _extract_product_cards(self, category: str) -> list[Product]:
        """Extract products from the current listing page."""
        products: list[Product] = []

        # Boodmo uses product card elements — try multiple selectors
        card_selectors = [
            ".product-card",
            ".catalog-item",
            "[class*='product-item']",
            ".search-result-item",
            "article[class*='product']",
        ]

        cards = []
        for sel in card_selectors:
            cards = await self.page.query_selector_all(sel)
            if cards:
                break

        if not cards:
            logger.debug("[boodmo] No product cards found on page")
            return products

        for card in cards:
            try:
                product = await self._parse_boodmo_card(card, category)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[boodmo] Failed to parse card: %s", e)
                continue

        return products

    async def _parse_boodmo_card(self, card, category: str) -> Product | None:
        """Parse a single Boodmo product card element."""
        # Product name
        name_el = await card.query_selector(
            "h2, h3, .product-name, .product-title, [class*='title']"
        )
        name = (await name_el.inner_text()).strip() if name_el else ""
        if not name:
            return None

        # Price
        price_el = await card.query_selector(
            ".price, .product-price, [class*='price']"
        )
        price_text = (await price_el.inner_text()).strip() if price_el else "0"
        price = self._parse_price(price_text)

        # Brand
        brand_el = await card.query_selector(
            ".brand, .product-brand, [class*='brand'], [class*='manufacturer']"
        )
        brand = (await brand_el.inner_text()).strip() if brand_el else ""

        # Part number
        part_el = await card.query_selector(
            ".part-number, .sku, [class*='part-num'], [class*='sku']"
        )
        part_number = (await part_el.inner_text()).strip() if part_el else ""

        # Product URL
        link_el = await card.query_selector("a[href]")
        href = (await link_el.get_attribute("href")) if link_el else ""
        url = href if href and href.startswith("http") else f"{self.base_url}{href}" if href else ""

        # Product ID from URL or part number
        product_id = part_number or self._extract_id_from_url(url)

        # Vehicle info from product name (common pattern: "Part Name for Make Model")
        vehicle_make, vehicle_model = self._parse_vehicle_from_name(name)

        return self._make_product(
            product_id=product_id,
            name=name,
            category=category,
            brand=brand,
            part_number=part_number,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vehicle_type=",".join(self.vehicle_types),
            price=price,
            url=url,
        )

    @staticmethod
    def _parse_price(text: str) -> float:
        """Extract numeric price from text like '₹1,234.00' or 'Rs. 1234'."""
        # Find the first number (with optional decimals) in the string
        match = re.search(r"(\d[\d,]*\.?\d*)", text)
        if not match:
            return 0.0
        cleaned = match.group(1).replace(",", "")
        try:
            return float(cleaned)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _extract_id_from_url(url: str) -> str:
        """Try to extract a product ID from the URL path."""
        if not url:
            return ""
        parts = url.rstrip("/").split("/")
        return parts[-1] if parts else ""

    @staticmethod
    def _parse_vehicle_from_name(name: str) -> tuple[str, str]:
        """Best-effort extraction of vehicle make/model from product name.

        Common patterns:
        - 'Brake Pad for Maruti Swift'
        - 'Hyundai Creta Front Bumper'
        """
        # Known Indian makes
        makes = [
            "Maruti Suzuki", "Maruti", "Hyundai", "Tata", "Mahindra",
            "Honda", "Toyota", "Kia", "MG", "Renault", "Nissan",
            "Volkswagen", "Skoda", "Ford", "Chevrolet", "Suzuki",
            "Hero", "Bajaj", "TVS", "Royal Enfield", "Yamaha",
            "KTM", "Kawasaki", "BMW", "Mercedes", "Audi",
        ]
        name_lower = name.lower()
        for make in makes:
            if make.lower() in name_lower:
                # Try to grab the next word as model
                idx = name_lower.index(make.lower())
                after = name[idx + len(make):].strip()
                model = after.split()[0] if after.split() else ""
                # Clean up model — remove common non-model words
                if model.lower() in {"for", "of", "the", "-", "–", "|", ""}:
                    model = ""
                return make, model
        return "", ""


# ---------------------------------------------------------------------------
# Autozilla (Magento)
# ---------------------------------------------------------------------------


class AutozillaScraper(PlaywrightScraper):
    """Scraper for autozilla.co — Magento-based platform.

    Strategy:
    1. Get category tree from main navigation.
    2. Scrape product listing pages per category.
    3. Extract product data from Magento's standard listing grid.
    """

    async def scrape(self, max_pages: int = MAX_PAGES) -> list[Product]:
        products: list[Product] = []
        try:
            await self._launch_browser()
            categories = await self._get_categories()
            logger.info("[autozilla] Found %d categories", len(categories))

            pages_scraped = 0
            for cat_name, cat_url in categories:
                if pages_scraped >= max_pages:
                    break
                page_products, pages_used = await self._scrape_category(
                    cat_name, cat_url, max_pages - pages_scraped
                )
                products.extend(page_products)
                pages_scraped += pages_used
        except Exception as e:
            logger.error("[autozilla] Scrape failed: %s", e)
            await self._screenshot_on_error("scrape_error")
        finally:
            await self._close_browser()

        logger.info("[autozilla] Total products scraped: %d", len(products))
        return products

    async def _get_categories(self) -> list[tuple[str, str]]:
        """Get category URLs from Magento navigation."""
        if not await self._navigate(self.base_url):
            await self._screenshot_on_error("home_load")
            return []

        # Magento standard nav selectors
        nav_selectors = [
            "nav.navigation a",
            ".nav-sections a",
            "#store\\.menu a",
            ".category-list a",
            "ul.nav a[href*='/']",
        ]

        links = []
        for sel in nav_selectors:
            try:
                links = await self.page.query_selector_all(sel)
                if links:
                    break
            except Exception:
                continue

        categories: list[tuple[str, str]] = []
        seen: set[str] = set()
        for link in links:
            try:
                href = await link.get_attribute("href") or ""
                text = (await link.inner_text()).strip()
                if (
                    href
                    and text
                    and href not in seen
                    and not href.endswith("#")
                    and self.base_url in href
                ):
                    categories.append((text, href))
                    seen.add(href)
            except Exception:
                continue

        return categories

    async def _scrape_category(
        self, cat_name: str, cat_url: str, remaining_pages: int
    ) -> tuple[list[Product], int]:
        """Scrape products from a Magento category listing."""
        products: list[Product] = []
        pages_used = 0

        if not await self._navigate(cat_url):
            return products, 0

        pages_used += 1
        page_products = await self._extract_listing_products(cat_name)
        products.extend(page_products)

        # Magento pagination
        while pages_used < remaining_pages:
            next_link = await self.page.query_selector(
                "a.action.next, .pages-item-next a, a[title='Next']"
            )
            if not next_link:
                break

            try:
                await next_link.click()
                await self.page.wait_for_load_state("networkidle", timeout=15000)
                pages_used += 1
                page_products = await self._extract_listing_products(cat_name)
                products.extend(page_products)
                await asyncio.sleep(self._delay)
            except Exception as e:
                logger.warning("[autozilla] Pagination failed in %s: %s", cat_name, e)
                break

        return products, pages_used

    async def _extract_listing_products(self, category: str) -> list[Product]:
        """Extract products from Magento product listing grid."""
        products: list[Product] = []

        # Magento product item selectors
        item_selectors = [
            ".product-item",
            ".products-grid .item",
            ".product-items li",
            "[class*='product-item']",
        ]

        items = []
        for sel in item_selectors:
            items = await self.page.query_selector_all(sel)
            if items:
                break

        if not items:
            logger.debug("[autozilla] No product items found on page")
            return products

        for item in items:
            try:
                product = await self._parse_magento_item(item, category)
                if product:
                    products.append(product)
            except Exception as e:
                logger.debug("[autozilla] Failed to parse item: %s", e)
                continue

        return products

    async def _parse_magento_item(self, item, category: str) -> Product | None:
        """Parse a Magento product list item."""
        # Product name
        name_el = await item.query_selector(
            ".product-item-name, .product-name, .product-item-link"
        )
        name = (await name_el.inner_text()).strip() if name_el else ""
        if not name:
            return None

        # Price — Magento uses .price wrapper
        price_el = await item.query_selector(
            ".price, .product-price, [data-price-type='finalPrice'] .price"
        )
        price_text = (await price_el.inner_text()).strip() if price_el else "0"
        price = BoodmoScraper._parse_price(price_text)

        # Product URL
        link_el = await item.query_selector("a.product-item-link, a[href]")
        href = (await link_el.get_attribute("href")) if link_el else ""
        url = href or ""

        # Try to get brand/part number from attributes or description
        brand = ""
        part_number = ""
        detail_els = await item.query_selector_all(
            ".product-item-attribute, .product-attribute, [class*='attribute']"
        )
        for el in detail_els:
            try:
                text = (await el.inner_text()).strip().lower()
                if "brand" in text or "manufacturer" in text:
                    brand = text.split(":")[-1].strip().title()
                elif "part" in text or "sku" in text:
                    part_number = text.split(":")[-1].strip()
            except Exception:
                continue

        product_id = part_number or BoodmoScraper._extract_id_from_url(url)
        vehicle_make, vehicle_model = BoodmoScraper._parse_vehicle_from_name(name)

        return self._make_product(
            product_id=product_id,
            name=name,
            category=category,
            brand=brand,
            part_number=part_number,
            vehicle_make=vehicle_make,
            vehicle_model=vehicle_model,
            vehicle_type=",".join(self.vehicle_types),
            price=price,
            url=url,
        )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _build_scrapers() -> list[PlaywrightScraper]:
    """Instantiate all configured Playwright scrapers."""
    scrapers: list[PlaywrightScraper] = []
    target_map = {
        "boodmo": BoodmoScraper,
        "autozilla": AutozillaScraper,
    }
    for name, cfg in PLAYWRIGHT_TARGETS.items():
        cls = target_map.get(name)
        if cls:
            scrapers.append(
                cls(
                    name=name,
                    base_url=cfg["base_url"],
                    vehicle_types=cfg["vehicle_types"],
                )
            )
        else:
            logger.warning("No scraper class for target: %s", name)
    return scrapers


async def scrape_all_playwright(max_pages: int = MAX_PAGES) -> list[Product]:
    """Run all Playwright scrapers sequentially and return combined products.

    Sequential to avoid overwhelming targets and to share a single browser.
    """
    all_products: list[Product] = []
    scrapers = _build_scrapers()

    for scraper in scrapers:
        logger.info("Starting %s scraper...", scraper.name)
        try:
            products = await scraper.scrape(max_pages=max_pages)
            all_products.extend(products)
            logger.info("%s: scraped %d products", scraper.name, len(products))
        except Exception as e:
            logger.error("%s scraper failed: %s", scraper.name, e)

    return all_products


def save_products(products: list[Product], output_path: Path | str) -> None:
    """Write products to a JSONL file (one JSON object per line)."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for product in products:
            f.write(json.dumps(product.to_dict(), ensure_ascii=False) + "\n")
    logger.info("Saved %d products to %s", len(products), output_path)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    products = asyncio.run(scrape_all_playwright())
    if products:
        out = RAW_DIR / "playwright_products.jsonl"
        save_products(products, out)
        print(f"Done. {len(products)} products saved to {out}")
    else:
        print("No products scraped.")
