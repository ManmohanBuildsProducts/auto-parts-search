"""NHTSA vPIC vehicle taxonomy scraper for knowledge graph.

Pulls vehicle makes, models, model years, and vehicle types from the NHTSA
Vehicle Product Information Catalog (vPIC) API for Indian-relevant brands.

API: https://vpic.nhtsa.dot.gov/api/
- Free, no auth required
- Endpoints used:
  - GetVehicleTypesForMakeId/{makeId} — vehicle types per make
  - GetModelsForMakeIdYear/makeId/{id}/modelyear/{year}/vehicletype/{type}
    — models with vehicle type classification

Indian-relevant makes present in vPIC: Suzuki, Hyundai, Honda, Toyota, Kia,
Nissan, Yamaha, Mahindra, Bajaj.
Not in vPIC (no US sales): Tata, Hero MotoCorp, TVS, Maruti (listed under Suzuki).
"""
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR, USER_AGENT

logger = logging.getLogger(__name__)

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api/vehicles"

# Indian-relevant makes with their vPIC Make_IDs.
# Tata, Hero MotoCorp, TVS are absent from vPIC (no US market presence).
# Maruti Suzuki is listed under SUZUKI.
INDIAN_RELEVANT_MAKES = {
    "SUZUKI": 509,       # covers Maruti Suzuki models
    "HYUNDAI": 498,
    "HONDA": 474,
    "TOYOTA": 448,
    "KIA": 499,
    "NISSAN": 478,
    "YAMAHA": 564,
    "MAHINDRA": 2146,
    "BAJAJ AUTO": 4007,
}

# Year range — vPIC has data going back decades, but 2005+ is most relevant
# for Indian auto parts market
YEAR_START = 2005
YEAR_END = 2026


def fetch_json(session: requests.Session, url: str) -> dict:
    """Fetch JSON from vPIC API with retry."""
    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if attempt < 2:
                logger.warning(f"Retry {attempt + 1} for {url}: {e}")
                time.sleep(2)
            else:
                logger.error(f"Failed after 3 attempts: {url}: {e}")
                return {"Results": [], "Count": 0}
    return {"Results": [], "Count": 0}


def fetch_vehicle_types(session: requests.Session, make_id: int) -> list[dict]:
    """Fetch vehicle types for a make."""
    url = f"{VPIC_BASE}/GetVehicleTypesForMakeId/{make_id}?format=json"
    data = fetch_json(session, url)
    return data.get("Results", [])


def fetch_models_for_year_type(
    session: requests.Session, make_id: int, year: int, vehicle_type: str
) -> list[dict]:
    """Fetch models for a specific make + year + vehicle type."""
    encoded_type = quote(vehicle_type)
    url = (
        f"{VPIC_BASE}/GetModelsForMakeIdYear/makeId/{make_id}"
        f"/modelyear/{year}/vehicletype/{encoded_type}?format=json"
    )
    data = fetch_json(session, url)
    return data.get("Results", [])


def scrape_nhtsa_vehicles() -> dict:
    """Scrape vehicle taxonomy from NHTSA vPIC API.

    Strategy:
    1. For each make, get its vehicle types via GetVehicleTypesForMakeId.
    2. For each make/year/vehicletype combo, query GetModelsForMakeIdYear
       with the vehicletype filter — this returns VehicleTypeName per model.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    vehicles = []
    seen = set()  # dedupe key: (make_id, model_id, year, vehicle_type_id)
    total_api_calls = 0

    for make_name, make_id in INDIAN_RELEVANT_MAKES.items():
        logger.info(f"Processing {make_name} (ID: {make_id})...")

        # Step 1: Get vehicle types for this make
        vtypes = fetch_vehicle_types(session, make_id)
        total_api_calls += 1
        type_names = [vt["VehicleTypeName"] for vt in vtypes]
        logger.info(f"  Vehicle types: {type_names}")
        time.sleep(0.5)

        # Step 2: For each year and vehicle type, get models
        years = range(YEAR_START, YEAR_END + 1)
        for year in years:
            for vt in vtypes:
                vt_name = vt["VehicleTypeName"]
                vt_id = vt["VehicleTypeId"]

                models = fetch_models_for_year_type(session, make_id, year, vt_name)
                total_api_calls += 1

                for m in models:
                    model_id = m.get("Model_ID")
                    model_name = m.get("Model_Name", "")
                    key = (make_id, model_id, year, vt_id)

                    if key in seen:
                        continue
                    seen.add(key)

                    vehicles.append({
                        "make": make_name,
                        "make_id": make_id,
                        "model": model_name,
                        "model_id": model_id,
                        "model_year": year,
                        "vehicle_type": vt_name,
                    })

                time.sleep(0.5)

            if year % 5 == 0:
                year_count = sum(1 for v in vehicles if v["make"] == make_name and v["model_year"] == year)
                logger.info(f"  {make_name} {year}: {year_count} models across {len(vtypes)} types")

        make_total = sum(1 for v in vehicles if v["make"] == make_name)
        logger.info(f"  {make_name} subtotal: {make_total} records")

    # Sort for stable output
    vehicles.sort(key=lambda v: (v["make"], v["model"], v["model_year"], v["vehicle_type"]))

    # Compute stats
    unique_makes = set(v["make"] for v in vehicles)
    unique_models = set((v["make"], v["model"]) for v in vehicles)
    unique_types = set(v["vehicle_type"] for v in vehicles)

    stats = {
        "total_api_calls": total_api_calls,
        "total_vehicles": len(vehicles),
        "unique_makes": len(unique_makes),
        "unique_models": len(unique_models),
        "unique_vehicle_types": len(unique_types),
        "vehicle_types": sorted(unique_types),
        "year_range": f"{YEAR_START}-{YEAR_END}",
        "makes": sorted(unique_makes),
    }

    logger.info(
        f"Done. {stats['total_vehicles']} vehicle records, "
        f"{stats['unique_makes']} makes, {stats['unique_models']} models, "
        f"{stats['unique_vehicle_types']} vehicle types"
    )

    return {"vehicles": vehicles, "stats": stats}


def save_vehicles(data: dict, output_path: Path) -> None:
    """Save vehicle taxonomy to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": {
            "description": "NHTSA vPIC vehicle taxonomy for Indian-relevant makes",
            "source": "https://vpic.nhtsa.dot.gov/api/",
            "makes_queried": list(INDIAN_RELEVANT_MAKES.keys()),
            "year_range": f"{YEAR_START}-{YEAR_END}",
            "note": "Tata, Hero MotoCorp, TVS absent from vPIC (no US market). Maruti Suzuki listed under SUZUKI.",
        },
        "stats": data["stats"],
        "vehicles": data["vehicles"],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(data['vehicles'])} vehicles to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_file = KNOWLEDGE_GRAPH_DIR / "nhtsa_vehicles.json"
    data = scrape_nhtsa_vehicles()
    save_vehicles(data, output_file)

    print(f"\nDone. {data['stats']['total_vehicles']} vehicle records saved to {output_file}")
    print(f"Makes: {data['stats']['unique_makes']}, Models: {data['stats']['unique_models']}")
    print(f"Vehicle types: {data['stats']['vehicle_types']}")
    print(f"\nPer-make breakdown:")
    from collections import Counter
    make_counts = Counter(v["make"] for v in data["vehicles"])
    for make, count in make_counts.most_common():
        models = len(set(v["model"] for v in data["vehicles"] if v["make"] == make))
        types = sorted(set(v["vehicle_type"] for v in data["vehicles"] if v["make"] == make))
        print(f"  {make}: {count} records ({models} models) — {types}")
