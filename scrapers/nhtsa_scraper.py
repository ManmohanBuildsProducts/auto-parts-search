"""NHTSA Recalls scraper for auto parts knowledge graph.

Pulls recall data from NHTSA (National Highway Traffic Safety Administration)
for Indian-relevant vehicle makes. Extracts component-to-vehicle cross-references
from recall records.

API: https://api.nhtsa.gov/recalls/recallsByVehicle
- Free, no auth required
- Requires make + model + modelYear (all three needed for results)
- Returns recall records with Component field containing hierarchical part categories

Indian-relevant makes: Suzuki (Maruti), Hyundai, Honda, Toyota, Kia, Nissan
Note: Tata and Mahindra are not sold in the US, so no NHTSA data exists for them.
"""
import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR, USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)

RECALLS_API = "https://api.nhtsa.gov/recalls/recallsByVehicle"

# Indian-relevant makes and their popular models (sold in both India and US markets)
# Tata and Mahindra are excluded — no US sales, no NHTSA data.
INDIAN_RELEVANT_VEHICLES = {
    "SUZUKI": [
        "SWIFT", "VITARA", "BALENO", "S-CROSS", "JIMNY",
        "SX4", "KIZASHI", "GRAND VITARA", "XL-7", "AERIO",
    ],
    "HYUNDAI": [
        "CRETA", "VENUE", "TUCSON", "VERNA", "I20",
        "ELANTRA", "SONATA", "SANTA FE", "KONA", "ACCENT",
        "I10", "IONIQ", "PALISADE",
    ],
    "HONDA": [
        "CITY", "CIVIC", "ACCORD", "CR-V", "HR-V",
        "JAZZ", "FIT", "AMAZE", "WR-V", "BR-V",
        "PILOT", "ODYSSEY",
    ],
    "TOYOTA": [
        "INNOVA", "FORTUNER", "CAMRY", "COROLLA", "RAV4",
        "YARIS", "GLANZA", "HILUX", "LAND CRUISER",
        "HIGHLANDER", "TACOMA", "4RUNNER",
    ],
    "KIA": [
        "SELTOS", "SONET", "CARNIVAL", "SPORTAGE", "FORTE",
        "SOUL", "TELLURIDE", "SORENTO", "K5",
    ],
    "NISSAN": [
        "MAGNITE", "KICKS", "ROGUE", "ALTIMA", "SENTRA",
        "PATHFINDER", "FRONTIER", "VERSA", "MAXIMA",
    ],
}

# Year range to query (NHTSA data is US-centric, go back to 2010 for relevance)
YEAR_START = 2010
YEAR_END = 2026


def fetch_recalls(
    session: requests.Session, make: str, model: str, year: int
) -> list[dict]:
    """Fetch recalls for a specific make/model/year from NHTSA API."""
    params = {"make": make, "model": model, "modelYear": str(year)}
    try:
        resp = session.get(RECALLS_API, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch {make} {model} {year}: {e}")
        return []


def parse_component(component_str: str) -> dict:
    """Parse NHTSA component string into structured hierarchy.

    Example: "FUEL SYSTEM, GASOLINE:DELIVERY:FUEL PUMP"
    Returns: {"system": "FUEL SYSTEM, GASOLINE", "subsystem": "DELIVERY", "component": "FUEL PUMP"}
    """
    parts = [p.strip() for p in component_str.split(":")]
    result = {"raw": component_str}
    if len(parts) >= 1:
        result["system"] = parts[0]
    if len(parts) >= 2:
        result["subsystem"] = parts[1]
    if len(parts) >= 3:
        result["component"] = parts[2]
    if len(parts) >= 4:
        result["detail"] = ":".join(parts[3:])
    return result


def scrape_nhtsa_recalls() -> dict:
    """Scrape NHTSA recalls for all Indian-relevant vehicles.

    Returns a dict with:
    - recalls: list of recall records
    - component_vehicle_map: component → list of vehicles
    - stats: summary statistics
    """
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_recalls = []
    seen_campaigns = set()  # deduplicate across make/model/year queries
    component_vehicle_map = defaultdict(set)
    skipped_empty = 0
    total_queries = 0

    total_combos = sum(len(models) for models in INDIAN_RELEVANT_VEHICLES.values())
    total_expected = total_combos * (YEAR_END - YEAR_START + 1)
    logger.info(
        f"Querying {len(INDIAN_RELEVANT_VEHICLES)} makes, "
        f"{total_combos} models, years {YEAR_START}-{YEAR_END} "
        f"({total_expected} API calls)"
    )

    for make, models in INDIAN_RELEVANT_VEHICLES.items():
        logger.info(f"Processing {make} ({len(models)} models)...")
        for model in models:
            for year in range(YEAR_START, YEAR_END + 1):
                total_queries += 1
                results = fetch_recalls(session, make, model, year)

                if not results:
                    skipped_empty += 1
                else:
                    for rec in results:
                        campaign = rec.get("NHTSACampaignNumber", "")
                        rec_key = f"{campaign}:{rec.get('Make', '')}:{rec.get('Model', '')}:{rec.get('ModelYear', '')}"
                        if rec_key in seen_campaigns:
                            continue
                        seen_campaigns.add(rec_key)

                        component_raw = rec.get("Component", "")
                        parsed = parse_component(component_raw)

                        recall_record = {
                            "campaign_number": campaign,
                            "make": rec.get("Make", ""),
                            "model": rec.get("Model", ""),
                            "model_year": rec.get("ModelYear", ""),
                            "manufacturer": rec.get("Manufacturer", ""),
                            "component_raw": component_raw,
                            "component_parsed": parsed,
                            "summary": rec.get("Summary", ""),
                            "consequence": rec.get("Consequence", ""),
                            "remedy": rec.get("Remedy", ""),
                            "report_date": rec.get("ReportReceivedDate", ""),
                        }
                        all_recalls.append(recall_record)

                        # Build component → vehicle mapping
                        vehicle_key = f"{rec.get('Make', '')}|{rec.get('Model', '')}|{rec.get('ModelYear', '')}"
                        component_vehicle_map[component_raw].add(vehicle_key)

                if total_queries % 50 == 0:
                    logger.info(
                        f"  Progress: {total_queries}/{total_expected} queries, "
                        f"{len(all_recalls)} recalls found"
                    )

                time.sleep(0.5)  # NHTSA is a free public API, 0.5s is polite

    # Convert sets to sorted lists for JSON serialization
    component_vehicle_map_serializable = {
        component: sorted(vehicles)
        for component, vehicles in sorted(component_vehicle_map.items())
    }

    # Build cross-reference summary: component → unique vehicles (without year)
    component_crossref = defaultdict(set)
    for component, vehicles in component_vehicle_map.items():
        parsed = parse_component(component)
        # Use the most specific component name available
        comp_name = parsed.get("component", parsed.get("subsystem", parsed.get("system", component)))
        for v in vehicles:
            make_model = "|".join(v.split("|")[:2])  # drop year
            component_crossref[comp_name].add(make_model)

    component_crossref_serializable = {
        comp: sorted(vehicles)
        for comp, vehicles in sorted(component_crossref.items())
    }

    stats = {
        "total_queries": total_queries,
        "empty_queries": skipped_empty,
        "total_recalls": len(all_recalls),
        "unique_campaigns": len({r["campaign_number"] for r in all_recalls}),
        "unique_components": len(component_vehicle_map),
        "unique_component_names": len(component_crossref),
        "makes_queried": list(INDIAN_RELEVANT_VEHICLES.keys()),
    }

    logger.info(
        f"Done. {stats['total_recalls']} recalls, "
        f"{stats['unique_components']} unique components, "
        f"{stats['unique_campaigns']} unique campaigns"
    )

    return {
        "recalls": all_recalls,
        "component_vehicle_map": component_vehicle_map_serializable,
        "component_crossref": component_crossref_serializable,
        "stats": stats,
    }


def save_recalls(data: dict, output_path: Path) -> None:
    """Save recall data to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": {
            "description": "NHTSA Recall data for Indian-relevant vehicle makes",
            "source": "https://api.nhtsa.gov/recalls/recallsByVehicle",
            "makes": list(INDIAN_RELEVANT_VEHICLES.keys()),
            "year_range": f"{YEAR_START}-{YEAR_END}",
            "note": "Tata and Mahindra excluded — no US sales, no NHTSA data",
        },
        "stats": data["stats"],
        "component_crossref": data["component_crossref"],
        "component_vehicle_map": data["component_vehicle_map"],
        "recalls": data["recalls"],
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_file = KNOWLEDGE_GRAPH_DIR / "nhtsa_recalls.json"
    data = scrape_nhtsa_recalls()
    save_recalls(data, output_file)

    print(f"\nDone. {data['stats']['total_recalls']} recalls saved to {output_file}")
    print(f"Unique components: {data['stats']['unique_components']}")
    print(f"Unique campaigns: {data['stats']['unique_campaigns']}")
    print(f"\nTop 10 components by vehicle coverage:")
    crossref = data["component_crossref"]
    top = sorted(crossref.items(), key=lambda x: len(x[1]), reverse=True)[:10]
    for comp, vehicles in top:
        print(f"  {comp}: {len(vehicles)} vehicles")
