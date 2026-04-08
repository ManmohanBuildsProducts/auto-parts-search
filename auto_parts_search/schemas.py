"""Data schemas for auto parts products and training pairs."""
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Product:
    """Normalized auto parts product."""
    source: str
    product_id: str
    name: str
    category: str = ""
    subcategory: str = ""
    brand: str = ""
    part_number: str = ""
    vehicle_make: str = ""
    vehicle_model: str = ""
    vehicle_year: str = ""
    vehicle_variant: str = ""
    vehicle_type: str = ""  # 2W, 4W, CV
    price: float = 0.0
    description: str = ""
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def search_text(self) -> str:
        """Text representation for embedding."""
        parts = [self.name]
        if self.brand:
            parts.append(self.brand)
        if self.vehicle_make:
            parts.append(self.vehicle_make)
        if self.vehicle_model:
            parts.append(self.vehicle_model)
        if self.vehicle_year:
            parts.append(str(self.vehicle_year))
        if self.category:
            parts.append(self.category)
        return " ".join(parts)


@dataclass
class TrainingPair:
    """A training pair for embedding model fine-tuning."""
    text_a: str
    text_b: str
    label: float  # 1.0 = similar, 0.0 = dissimilar
    pair_type: str  # synonym, misspelling, symptom, brand_generic, catalog, negative
    source: str = ""  # where this pair came from

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BenchmarkQuery:
    """A benchmark evaluation query."""
    query: str
    query_type: str  # exact_english, hindi_hinglish, misspelled, symptom, part_number, brand_as_generic
    expected_parts: list[str] = field(default_factory=list)  # expected part types/names
    expected_categories: list[str] = field(default_factory=list)
    expected_vehicles: list[str] = field(default_factory=list)
    difficulty: str = "medium"  # easy, medium, hard
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)
