"""Tests for catalog-based training pair generation."""
import json
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.schemas import Product
from training.catalog_pairs import (
    load_products,
    group_products,
    generate_positive_pairs,
    generate_negative_pairs,
)


def _make_products() -> list[Product]:
    """Create test products across different categories and vehicles."""
    return [
        Product(source="test", product_id="1", name="Brake Pad Front", category="Brake System", brand="Bosch", vehicle_make="Maruti", vehicle_model="Swift"),
        Product(source="test", product_id="2", name="Brake Disc Rotor", category="Brake System", brand="Brembo", vehicle_make="Maruti", vehicle_model="Swift"),
        Product(source="test", product_id="3", name="Brake Pad Rear", category="Brake System", brand="Rane", vehicle_make="Maruti", vehicle_model="Swift"),
        Product(source="test", product_id="4", name="Oil Filter", category="Service Parts", brand="Bosch", vehicle_make="Maruti", vehicle_model="Swift"),
        Product(source="test", product_id="5", name="Air Filter", category="Service Parts", brand="Bosch", vehicle_make="Maruti", vehicle_model="Swift"),
        Product(source="test", product_id="6", name="Spark Plug", category="Service Parts", brand="NGK", vehicle_make="Hyundai", vehicle_model="Creta"),
        Product(source="test", product_id="7", name="Shock Absorber Front", category="Suspension", brand="Monroe", vehicle_make="Hyundai", vehicle_model="Creta"),
        Product(source="test", product_id="8", name="Shock Absorber Rear", category="Suspension", brand="KYB", vehicle_make="Hyundai", vehicle_model="Creta"),
    ]


def test_load_products():
    products = _make_products()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        for p in products:
            f.write(json.dumps(p.to_dict()) + "\n")
        f.flush()
        loaded = load_products(Path(f.name))
    assert len(loaded) == 8
    assert loaded[0].name == "Brake Pad Front"


def test_group_products():
    products = _make_products()
    groups = group_products(products)
    # Should have groups for brake|maruti|swift, service|maruti|swift, etc.
    assert len(groups) >= 3
    # Brake System + Maruti + Swift should have 3 products
    brake_swift_key = "brake system|maruti|swift"
    assert brake_swift_key in groups
    assert len(groups[brake_swift_key]) == 3


def test_generate_positive_pairs():
    products = _make_products()
    groups = group_products(products)
    pairs = generate_positive_pairs(groups)
    assert len(pairs) > 0
    for p in pairs:
        assert p.label == 1.0
        assert p.pair_type == "catalog_positive"
        assert p.text_a != ""
        assert p.text_b != ""


def test_generate_negative_pairs():
    products = _make_products()
    negatives = generate_negative_pairs(products, num_positives=5, ratio=2)
    assert len(negatives) > 0
    for p in negatives:
        assert p.label == 0.0
        assert p.pair_type == "catalog_negative"


def test_no_self_pairs():
    products = _make_products()
    groups = group_products(products)
    pairs = generate_positive_pairs(groups)
    for p in pairs:
        assert p.text_a != p.text_b
