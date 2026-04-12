"""Generate training pairs from scraped product catalog data.

Takes normalized product data and generates embedding training pairs:
- Positive pairs: products in same category for same vehicle (label=1.0)
- Negative pairs: products in different categories (label=0.0)
"""
import json
import random
from pathlib import Path
from collections import defaultdict

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import Product, TrainingPair
from auto_parts_search.config import TRAINING_DIR, RAW_DIR, NEGATIVE_RATIO, RANDOM_SEED

# ADR 009: deterministic pair generation via per-function Random(seed).
# Module-level seed retained as a fallback; per-function rng is the authoritative
# mechanism — it cannot be polluted by other modules calling random.*.
random.seed(RANDOM_SEED)


def load_products(input_path: Path) -> list[Product]:
    """Load products from JSONL file."""
    products = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            products.append(Product(**data))
    return products


def group_products(products: list[Product]) -> dict[str, list[Product]]:
    """Group products by category + vehicle for positive pair generation."""
    groups = defaultdict(list)
    for p in products:
        # Group key: category + vehicle_make + vehicle_model
        key_parts = []
        if p.category:
            key_parts.append(p.category.lower().strip())
        if p.vehicle_make:
            key_parts.append(p.vehicle_make.lower().strip())
        if p.vehicle_model:
            key_parts.append(p.vehicle_model.lower().strip())

        if len(key_parts) >= 1:  # at least category
            key = "|".join(key_parts)
            groups[key].append(p)
    return dict(groups)


def generate_positive_pairs(
    groups: dict[str, list[Product]],
    max_per_group: int = 10,
    seed: int = RANDOM_SEED,
) -> list[TrainingPair]:
    """Generate positive pairs from products in same group. Deterministic per seed."""
    rng = random.Random(seed)
    pairs = []
    for group_key, products in sorted(groups.items()):
        if len(products) < 2:
            continue
        # Sample pairs from the group
        n = min(max_per_group, len(products) * (len(products) - 1) // 2)
        seen = set()
        attempts = 0
        while len(seen) < n and attempts < n * 3:
            attempts += 1
            a, b = rng.sample(products, 2)
            pair_key = tuple(sorted([a.product_id, b.product_id]))
            if pair_key in seen:
                continue
            seen.add(pair_key)
            pairs.append(TrainingPair(
                text_a=a.search_text(),
                text_b=b.search_text(),
                label=1.0,
                pair_type="catalog_positive",
                source=f"group:{group_key}",
            ))
    return pairs


def generate_negative_pairs(
    products: list[Product],
    num_positives: int,
    ratio: int = NEGATIVE_RATIO,
    seed: int = RANDOM_SEED,
) -> list[TrainingPair]:
    """Generate negative pairs from products in different categories. Deterministic per seed."""
    rng = random.Random(seed)
    # Group by category for negative sampling
    by_category = defaultdict(list)
    for p in products:
        cat = p.category.lower().strip() if p.category else "unknown"
        by_category[cat].append(p)

    categories = sorted(by_category.keys())
    if len(categories) < 2:
        return []

    target = num_positives * ratio
    pairs = []
    seen = set()
    attempts = 0

    while len(pairs) < target and attempts < target * 3:
        attempts += 1
        cat_a, cat_b = rng.sample(categories, 2)
        a = rng.choice(by_category[cat_a])
        b = rng.choice(by_category[cat_b])
        pair_key = tuple(sorted([a.product_id, b.product_id]))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        pairs.append(TrainingPair(
            text_a=a.search_text(),
            text_b=b.search_text(),
            label=0.0,
            pair_type="catalog_negative",
            source=f"neg:{cat_a}|{cat_b}",
        ))

    return pairs


def generate_catalog_pairs(input_path: Path) -> list[TrainingPair]:
    """Generate all catalog-based training pairs from a product JSONL file."""
    products = load_products(input_path)
    if not products:
        print(f"No products found in {input_path}")
        return []

    print(f"Loaded {len(products)} products from {input_path}")

    groups = group_products(products)
    print(f"Grouped into {len(groups)} groups")

    positive_pairs = generate_positive_pairs(groups)
    print(f"Generated {len(positive_pairs)} positive pairs")

    negative_pairs = generate_negative_pairs(products, len(positive_pairs))
    print(f"Generated {len(negative_pairs)} negative pairs")

    return positive_pairs + negative_pairs


def save_pairs(pairs: list[TrainingPair], output_path: Path) -> None:
    """Save training pairs to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for pair in pairs:
            f.write(json.dumps(pair.to_dict(), ensure_ascii=False) + "\n")
    print(f"Saved {len(pairs)} pairs to {output_path}")


def generate_from_all_sources() -> list[TrainingPair]:
    """Generate catalog pairs from all available scraped data files."""
    all_pairs = []
    raw_files = list(RAW_DIR.glob("*.jsonl"))

    if not raw_files:
        print(f"No JSONL files found in {RAW_DIR}")
        print("Run scrapers first: python -m scrapers.shopify_scraper")
        return []

    for raw_file in raw_files:
        print(f"\n--- Processing {raw_file.name} ---")
        pairs = generate_catalog_pairs(raw_file)
        all_pairs.extend(pairs)

    return all_pairs


if __name__ == "__main__":
    pairs = generate_from_all_sources()
    if pairs:
        output = TRAINING_DIR / "catalog_pairs.jsonl"
        save_pairs(pairs, output)

        # Stats
        positive = sum(1 for p in pairs if p.label == 1.0)
        negative = sum(1 for p in pairs if p.label == 0.0)
        print(f"\nTotal: {len(pairs)} pairs ({positive} positive, {negative} negative)")
    else:
        print("\nNo pairs generated. Scrape product data first.")
