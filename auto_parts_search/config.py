"""Configuration for auto parts search pipeline."""
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
RESEARCH_DIR = PROJECT_ROOT.parent / "auto-parts-research"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
TRAINING_DIR = DATA_DIR / "training"
KNOWLEDGE_GRAPH_DIR = DATA_DIR / "knowledge_graph"

# Ensure directories exist
for d in [RAW_DIR, PROCESSED_DIR, TRAINING_DIR, KNOWLEDGE_GRAPH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Common product schema fields
PRODUCT_SCHEMA = [
    "source",           # platform name
    "product_id",       # platform-specific ID
    "name",             # product title
    "category",         # top-level category
    "subcategory",      # subcategory
    "brand",            # manufacturer/brand
    "part_number",      # OEM or aftermarket part number
    "vehicle_make",     # e.g., Maruti Suzuki
    "vehicle_model",    # e.g., Swift
    "vehicle_year",     # e.g., 2019
    "vehicle_variant",  # e.g., ZXI Petrol
    "vehicle_type",     # 2W, 4W, CV
    "price",            # in INR
    "description",      # product description text
    "url",              # product page URL
]

# Shopify scraping targets
SHOPIFY_TARGETS = {
    "spareshub": {
        "base_url": "https://spareshub.com",
        "products_url": "https://spareshub.com/products.json",
        "vehicle_types": ["4W"],
    },
    "bikespares": {
        "base_url": "https://bikespares.in",
        "products_url": "https://bikespares.in/products.json",
        "vehicle_types": ["2W"],
    },
    "eauto": {
        "base_url": "https://eauto.co.in",
        "products_url": "https://eauto.co.in/products.json",
        "vehicle_types": ["2W"],
    },
}

# Playwright scraping targets
PLAYWRIGHT_TARGETS = {
    "boodmo": {
        "base_url": "https://boodmo.com",
        "vehicle_types": ["4W", "2W"],
    },
    "autozilla": {
        "base_url": "https://www.autozilla.co",
        "vehicle_types": ["4W"],
    },
}

# Scraper settings
REQUEST_DELAY = 2.0  # seconds between requests
MAX_PAGES = 50       # max pages to scrape per target
USER_AGENT = "AutoPartsSearch/0.1 (Research; contact@example.com)"

# Training pair settings
POSITIVE_LABEL = 1.0
NEGATIVE_LABEL = 0.0
NEGATIVE_RATIO = 2  # negative pairs per positive pair

# Benchmark settings
BENCHMARK_QUERY_TYPES = [
    "exact_english",      # "brake pad Maruti Swift 2019"
    "hindi_hinglish",     # "swift ka shocker"
    "misspelled",         # "break pad", "klutch plate"
    "symptom",            # "engine garam ho raha hai"
    "part_number",        # "16510M68K00"
    "brand_as_generic",   # "Mobil for Swift", "Exide for Activa"
]
