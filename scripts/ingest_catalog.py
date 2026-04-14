"""T405 — Add scraped catalog products to the Meilisearch `parts` index.

Catalog sources in data/raw/:
  - shopify_products.jsonl    (24,865 rows; SparesHub/BikeSpares/eAuto — real
                               OEM part numbers in titles)
  - additional_products.jsonl (608 rows; mixed small sites)
  - playwright_products.jsonl (479 rows; autozilla)
  - boodmo_sitemap_products.jsonl (1.4M rows; generic part names, no vehicle
                               specificity — SKIP to avoid drowning the index)

Each product -> one Meilisearch doc:
  id              str    catalog_<source>_<product_id>  (unique)
  doc_type        'catalog'
  name            product title (as shown to user)
  brand           if present
  vehicle_make    if present
  vehicle_model   if present
  source          shopify_spareshub | autozilla | ...
  part_number     extracted from title via regex (best-effort)
  indexed_tokens  IndicTokenizer dual-script expansion

Usage:
    python3 -m scripts.ingest_catalog
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import requests

from auto_parts_search.search_bm25 import MEILI_URL, MEILI_KEY, INDEX_NAME, _headers
from auto_parts_search.tokenizer import IndicTokenizer

CATALOG_SOURCES = [
    Path("data/raw/shopify_products.jsonl"),
    Path("data/raw/additional_products.jsonl"),
    Path("data/raw/playwright_products.jsonl"),
]

# Extract alphanumeric tokens likely to be part numbers:
#   - 5+ chars
#   - mix of letters and digits, or all-digits
#   - NOT common words / sizes
PART_NUMBER_RE = re.compile(r"\b([A-Z0-9][A-Z0-9-]{4,})\b")
STOPWORDS_PN = {
    "FRONT", "REAR", "LEFT", "RIGHT", "UPPER", "LOWER", "GENUINE",
    "COMPLETE", "ASSEMBLY", "PLASTIC", "METAL", "BLACK", "WHITE",
    "HONDA", "HERO", "BAJAJ", "YAMAHA", "SUZUKI", "TVS", "MARUTI",
    "SWIFT", "DZIRE", "BREZZA", "WAGONR", "ALTO", "CRETA", "VERNA",
    "ACTIVA", "SPLENDOR", "BULLET", "PULSAR", "NEXON", "SCORPIO",
    "2019", "2020", "2021", "2022", "2023", "2024", "2025", "2026",
    "125CC", "150CC", "160CC", "180CC", "200CC", "250CC", "350CC",
    "RSCR", "OEM",
}


def extract_part_numbers(text: str) -> list[str]:
    if not text:
        return []
    hits = []
    for m in PART_NUMBER_RE.findall(text):
        if m.upper() in STOPWORDS_PN:
            continue
        if not any(c.isdigit() for c in m):
            continue  # part numbers must contain digits
        if not any(c.isalpha() for c in m) and len(m) < 7:
            continue  # all-digit tokens must be long enough
        hits.append(m)
    return hits[:3]  # cap


def load_catalog_rows() -> list[dict]:
    rows: list[dict] = []
    for src in CATALOG_SOURCES:
        if not src.exists():
            print(f"  SKIP missing: {src}")
            continue
        n = 0
        for line in src.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            name = (r.get("name") or "").strip()
            if not name or len(name) < 3:
                continue
            source = r.get("source", src.stem)
            pid = r.get("product_id") or f"n{n}"
            # Meilisearch doc ids: [a-zA-Z0-9-_]
            safe_id = f"cat_{source}_{pid}".replace("/", "_")
            safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", safe_id)[:480]
            rows.append({
                "id": safe_id,
                "doc_type": "catalog",
                "part_id": safe_id,
                "name": name,
                "aliases": [],
                "system": r.get("category", ""),
                "brand": r.get("brand", ""),
                "vehicle_make": r.get("vehicle_make", ""),
                "vehicle_model": r.get("vehicle_model", ""),
                "source": source,
                "part_numbers": extract_part_numbers(name),
                "_raw_description": (r.get("description") or "")[:300],
            })
            n += 1
        print(f"  loaded {n} from {src.name}")
    return rows


def expand_tokens(docs: list[dict], tok: IndicTokenizer) -> list[dict]:
    for d in docs:
        blob = " ".join(filter(None, [
            d["name"],
            d.get("brand", ""),
            d.get("vehicle_make", ""),
            d.get("vehicle_model", ""),
            d.get("system", ""),
            " ".join(d.get("part_numbers", [])),
        ]))
        d["indexed_tokens"] = tok.index_tokens(blob)
    return docs


def _meili(method: str, path: str, body=None) -> dict:
    url = f"{MEILI_URL}{path}"
    r = requests.request(method, url, headers=_headers(), json=body, timeout=120)
    r.raise_for_status()
    return r.json() if r.content else {}


def wait_for_task(task_uid: int, label: str = "") -> None:
    for _ in range(600):  # up to 5 min
        t = _meili("GET", f"/tasks/{task_uid}")
        if t["status"] == "succeeded":
            print(f"  {label} succeeded in {t.get('duration', 'n/a')}")
            return
        if t["status"] == "failed":
            raise RuntimeError(f"{label} failed: {t.get('error')}")
        time.sleep(0.5)
    raise RuntimeError(f"{label} timed out")


def main() -> None:
    print("building catalog docs...")
    rows = load_catalog_rows()
    tok = IndicTokenizer()
    rows = expand_tokens(rows, tok)
    print(f"total catalog docs: {len(rows)}")

    # Update index settings to include new fields
    _meili("PATCH", f"/indexes/{INDEX_NAME}/settings", {
        "searchableAttributes": [
            "name", "aliases", "indexed_tokens", "system",
            "part_numbers", "brand", "vehicle_make", "vehicle_model",
        ],
        "displayedAttributes": [
            "id", "part_id", "name", "aliases", "system", "doc_type",
            "brand", "vehicle_make", "vehicle_model", "source", "part_numbers",
        ],
        "filterableAttributes": ["doc_type", "source", "brand", "vehicle_make"],
    })

    # Push in 5K-doc batches
    BATCH = 5000
    n_batches = (len(rows) + BATCH - 1) // BATCH
    last_task = None
    for i in range(0, len(rows), BATCH):
        chunk = rows[i : i + BATCH]
        task = _meili("POST", f"/indexes/{INDEX_NAME}/documents", chunk)
        last_task = task["taskUid"]
        print(f"  batch {i//BATCH + 1}/{n_batches}: enqueued task {last_task} ({len(chunk)} docs)")

    wait_for_task(last_task, label="final batch")

    # Final stats
    stats = _meili("GET", f"/indexes/{INDEX_NAME}/stats")
    print(f"\nindex stats: {stats}")


if __name__ == "__main__":
    main()
