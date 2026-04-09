"""HSN Code Taxonomy scraper for auto parts knowledge graph.

Builds a hierarchical taxonomy of HSN (Harmonized System of Nomenclature) codes
for auto parts from open datasets:
- Chapter 8708: Parts and accessories of motor vehicles
- Chapter 84: Mechanical machinery/parts (engines, pumps, filters)
- Chapter 85: Electrical machinery/parts (starters, alternators, ignition)

Sources:
- datasets/harmonized-system (UN Comtrade, 6-digit level with parent-child)
- warrantgroup/WCO-HS-Codes (Indian Customs Tariff, 8/10-digit granularity)
"""
import csv
import io
import json
import logging
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from auto_parts_search.config import KNOWLEDGE_GRAPH_DIR, USER_AGENT, REQUEST_DELAY

logger = logging.getLogger(__name__)

# Open dataset URLs
HS_CSV_URL = (
    "https://raw.githubusercontent.com/datasets/harmonized-system"
    "/main/data/harmonized-system.csv"
)
WCO_CSV_URL = (
    "https://raw.githubusercontent.com/warrantgroup/WCO-HS-Codes"
    "/master/data/hscodes.csv"
)

# Chapters relevant to auto parts
TARGET_CHAPTERS = {"84", "85", "87"}
# Within chapter 87, we only want heading 8708 (parts & accessories)
CHAPTER_87_HEADINGS = {"8708"}

# Auto-parts relevant headings in chapters 84 and 85
# Curated from CBIC tariff schedule — headings with engine, pump, filter,
# starter, alternator, ignition, bearing, and similar auto components
AUTO_PARTS_HEADINGS_84 = {
    "8407",  # Spark-ignition reciprocating engines
    "8408",  # Compression-ignition engines (diesel)
    "8409",  # Parts for spark/compression-ignition engines
    "8410",  # Hydraulic turbines, water wheels (power steering pumps)
    "8411",  # Turbo-jets, turbo-propellers, gas turbines
    "8412",  # Engines and motors (hydraulic, pneumatic)
    "8413",  # Pumps (fuel pumps, oil pumps, water pumps)
    "8414",  # Air/vacuum pumps, compressors (AC compressors)
    "8415",  # Air conditioning machines
    "8421",  # Centrifuges, filtering machinery (oil/fuel/air filters)
    "8425",  # Pulleys, winches, jacks (car jacks)
    "8481",  # Taps, cocks, valves (engine valves)
    "8482",  # Ball/roller bearings
    "8483",  # Transmission shafts, cranks, bearing housings, gears
    "8484",  # Gaskets, mechanical seals
}

AUTO_PARTS_HEADINGS_85 = {
    "8501",  # Electric motors, generators
    "8504",  # Electrical transformers, converters (voltage regulators)
    "8507",  # Electric accumulators (batteries)
    "8511",  # Electrical ignition/starting equipment
    "8512",  # Electrical lighting/signalling equipment for vehicles
    "8516",  # Electric heaters (seat heaters, defoggers)
    "8536",  # Electrical switches, relays, fuses
    "8539",  # Electric filament/discharge lamps (headlamps)
    "8544",  # Insulated wire, cable (wiring harness)
}


def _is_target_code(code: str) -> bool:
    """Check if an HS code belongs to our target chapters/headings."""
    if len(code) < 2:
        return False
    chapter = code[:2]
    if chapter == "87":
        # Only 8708 and its subcodes within chapter 87
        return code.startswith("8708") or code == "87"
    if chapter == "84":
        if len(code) == 2:
            return True  # Chapter heading
        heading = code[:4]
        return heading in AUTO_PARTS_HEADINGS_84
    if chapter == "85":
        if len(code) == 2:
            return True  # Chapter heading
        heading = code[:4]
        return heading in AUTO_PARTS_HEADINGS_85
    return False


def _clean_description(desc: str) -> str:
    """Clean WCO description artifacts."""
    # Remove markup artifacts like <AG>!3!, <857>, <867>, <961>, <AC>, ++++
    import re
    desc = re.sub(r"<[A-Z]+>!?\d*!?", "", desc)
    desc = re.sub(r"<\d+>", "", desc)
    desc = desc.replace("++++", "")
    desc = re.sub(r"\s+", " ", desc).strip()
    # Truncate very long descriptions to the first meaningful segment
    if len(desc) > 200:
        # Keep up to the first colon-separated segment that's meaningful
        parts = desc.split(":")
        if len(parts) >= 2:
            # Keep heading + first sub-description
            short = ":".join(parts[:3]).strip()
            if len(short) > 200:
                short = short[:197] + "..."
            return short
    return desc


def _determine_level(code: str) -> int:
    """Determine hierarchy level from code length."""
    length = len(code)
    if length == 2:
        return 1  # Chapter
    if length == 4:
        return 2  # Heading
    if length == 6:
        return 3  # Subheading
    if length == 8:
        return 4  # Tariff item
    if length == 10:
        return 5  # National line
    return length // 2


def _determine_parent(code: str) -> str:
    """Determine parent code from code structure."""
    length = len(code)
    if length <= 2:
        return ""
    if length == 4:
        return code[:2]
    if length == 6:
        return code[:4]
    if length == 8:
        return code[:6]
    if length == 10:
        return code[:8]
    return code[:-2]


def fetch_csv(url: str, session: requests.Session) -> str:
    """Download a CSV file and return its text content."""
    logger.info(f"Fetching {url}")
    resp = session.get(url, timeout=60)
    resp.raise_for_status()
    return resp.text


def parse_harmonized_system(csv_text: str) -> dict[str, dict]:
    """Parse the datasets/harmonized-system CSV into a code dict.

    CSV columns: section, hscode, description, parent, level
    """
    codes = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        code = row["hscode"].strip()
        if not _is_target_code(code):
            continue
        codes[code] = {
            "code": code,
            "description": row["description"].strip().strip('"'),
            "parent_code": row["parent"].strip() if row["parent"] != "TOTAL" else "",
            "children": [],
            "level": _determine_level(code),
        }
    return codes


def parse_wco_codes(csv_text: str) -> dict[str, dict]:
    """Parse the WCO HS codes CSV for India-specific 8/10-digit codes.

    CSV columns: hscode, description
    """
    codes = {}
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        code = row["hscode"].strip()
        if not _is_target_code(code):
            continue
        # Skip 2/4/6-digit codes — we already have those from harmonized-system
        if len(code) <= 6:
            continue
        desc = _clean_description(row["description"].strip().strip('"'))
        codes[code] = {
            "code": code,
            "description": desc,
            "parent_code": _determine_parent(code),
            "children": [],
            "level": _determine_level(code),
        }
    return codes


def _synthesize_missing_parents(codes: dict[str, dict]) -> None:
    """Create missing intermediate 8-digit parent codes.

    The harmonized-system dataset has 6-digit codes and the WCO dataset has
    8/10-digit codes. The 8-digit parents of 10-digit codes often don't exist
    in either dataset, so we synthesize them from their children's descriptions.
    """
    missing = set()
    for code, entry in list(codes.items()):
        parent = entry["parent_code"]
        if parent and parent not in codes:
            missing.add(parent)

    for parent_code in missing:
        # Find children that reference this parent
        children = [c for c, e in codes.items() if e["parent_code"] == parent_code]
        # Derive description from the first child, trimming the last specific part
        desc = ""
        if children:
            child_desc = codes[children[0]]["description"]
            # Take description up to last colon for a more general label
            parts = child_desc.rsplit(":", 1)
            if len(parts) > 1:
                desc = parts[0].strip()
            else:
                desc = child_desc
        codes[parent_code] = {
            "code": parent_code,
            "description": desc,
            "parent_code": _determine_parent(parent_code),
            "children": [],
            "level": _determine_level(parent_code),
        }

    if missing:
        logger.info(f"Synthesized {len(missing)} intermediate parent codes")
        # Recurse to handle any newly created codes that also have missing parents
        still_missing = [c for c in codes if codes[c]["parent_code"] and codes[c]["parent_code"] not in codes]
        if still_missing:
            _synthesize_missing_parents(codes)


def build_hierarchy(codes: dict[str, dict]) -> list[dict]:
    """Wire up parent-child relationships and return root-level entries."""
    # Synthesize any missing intermediate parents first
    _synthesize_missing_parents(codes)

    # Build children lists
    for code, entry in codes.items():
        parent = entry["parent_code"]
        if parent and parent in codes:
            if code not in codes[parent]["children"]:
                codes[parent]["children"].append(code)

    # Sort children in each entry
    for entry in codes.values():
        entry["children"].sort()

    # Return all entries as a flat list (hierarchy is in parent/children refs)
    return sorted(codes.values(), key=lambda e: e["code"])


def validate_taxonomy(entries: list[dict], codes: dict[str, dict]) -> None:
    """Validate parent-child consistency."""
    issues = []
    for entry in entries:
        # Check parent exists (except roots)
        parent = entry["parent_code"]
        if parent and parent not in codes:
            issues.append(f"Orphan: {entry['code']} references missing parent {parent}")
        # Check children exist
        for child in entry["children"]:
            if child not in codes:
                issues.append(f"Ghost child: {entry['code']} lists missing child {child}")

    if issues:
        logger.warning(f"Validation found {len(issues)} issues:")
        for issue in issues[:10]:
            logger.warning(f"  {issue}")
    else:
        logger.info("Validation passed: all parent-child relationships consistent.")


def scrape_hsn_taxonomy() -> list[dict]:
    """Scrape and merge HSN codes from open datasets."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # Step 1: Fetch base hierarchy (2/4/6-digit) from harmonized-system
    hs_text = fetch_csv(HS_CSV_URL, session)
    codes = parse_harmonized_system(hs_text)
    logger.info(f"Harmonized system: {len(codes)} codes (2/4/6-digit)")

    time.sleep(REQUEST_DELAY)

    # Step 2: Fetch granular India-specific codes (8/10-digit) from WCO
    wco_text = fetch_csv(WCO_CSV_URL, session)
    wco_codes = parse_wco_codes(wco_text)
    logger.info(f"WCO India tariff: {len(wco_codes)} codes (8/10-digit)")

    # Merge: WCO codes supplement the base hierarchy
    codes.update(wco_codes)
    logger.info(f"Merged total: {len(codes)} codes")

    # Step 3: Build hierarchy
    entries = build_hierarchy(codes)

    # Step 4: Validate
    validate_taxonomy(entries, codes)

    return entries


def save_taxonomy(entries: list[dict], output_path: Path) -> None:
    """Save taxonomy to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output = {
        "metadata": {
            "description": "HSN Code Taxonomy for Indian Auto Parts",
            "chapters": {
                "84": "Mechanical machinery/parts (engines, pumps, filters, bearings)",
                "85": "Electrical machinery/parts (starters, alternators, ignition, batteries)",
                "8708": "Parts and accessories of motor vehicles",
            },
            "sources": [
                "datasets/harmonized-system (UN Comtrade)",
                "warrantgroup/WCO-HS-Codes (Indian Customs Tariff)",
            ],
            "total_codes": len(entries),
            "levels": {
                "1": "Chapter (2-digit)",
                "2": "Heading (4-digit)",
                "3": "Subheading (6-digit)",
                "4": "Tariff item (8-digit)",
                "5": "National line (10-digit)",
            },
        },
        "codes": entries,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(entries)} codes to {output_path}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    output_file = KNOWLEDGE_GRAPH_DIR / "hsn_taxonomy.json"
    entries = scrape_hsn_taxonomy()
    save_taxonomy(entries, output_file)

    # Summary stats
    levels = {}
    for e in entries:
        levels[e["level"]] = levels.get(e["level"], 0) + 1
    print(f"\nDone. {len(entries)} HSN codes saved to {output_file}")
    print("Codes by level:")
    for level in sorted(levels):
        label = {1: "Chapter", 2: "Heading", 3: "Subheading", 4: "Tariff item", 5: "National line"}.get(level, f"Level {level}")
        print(f"  {label} ({level}): {levels[level]}")
