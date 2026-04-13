"""Fetch Hindi auto-parts labels + aliases from Wikidata via SPARQL.

Zero-cost canonical vocabulary source. Covers direct + transitive subclasses
of Q46765731 (automotive part). Saves (qid, hindi_label, english_label,
aliases_hi, aliases_en) to a JSONL.

Usage:
    python3.11 -m scripts.fetch_wikidata_auto
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path("data/external/processed/wikidata_auto.jsonl")
ENDPOINT = "https://query.wikidata.org/sparql"

# Narrower query - auto part + common subcategories that actually have Hindi labels.
# P279* subclass-of* closure is slow / timeout-prone on Wikidata; we seed with
# known relevant top-level classes.
QUERY = """
SELECT DISTINCT ?item ?itemLabel ?itemLabel_hi ?alias_hi ?alias_en
WHERE {
  VALUES ?parent {
    wd:Q46765731   # automotive part
    wd:Q28731554   # motor vehicle component
    wd:Q11436      # engine
    wd:Q11389      # internal combustion engine
    wd:Q174814     # tire
    wd:Q173183     # spark plug
    wd:Q190095     # brake
    wd:Q1197829    # transmission
    wd:Q133895     # gearbox
    wd:Q170627     # clutch
    wd:Q177777     # suspension
    wd:Q182060     # carburetor
    wd:Q192242     # exhaust
    wd:Q170429     # piston
    wd:Q192386     # crankshaft
    wd:Q211395     # muffler
    wd:Q156487     # battery
    wd:Q172007     # alternator
    wd:Q11421      # bicycle (for 2W adjacent)
    wd:Q34493      # motorcycle
  }
  { ?item wdt:P279 ?parent . } UNION { ?item wdt:P31 ?parent . }
  OPTIONAL { ?item rdfs:label ?itemLabel_hi FILTER(lang(?itemLabel_hi) = "hi") }
  OPTIONAL { ?item skos:altLabel ?alias_hi FILTER(lang(?alias_hi) = "hi") }
  OPTIONAL { ?item skos:altLabel ?alias_en FILTER(lang(?alias_en) = "en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
}
LIMIT 5000
"""


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    url = f"{ENDPOINT}?query={urllib.parse.quote(QUERY)}&format=json"
    req = urllib.request.Request(url, headers={
        "User-Agent": "auto-parts-search/0.1 (github.com/ManmohanBuildsProducts/auto-parts-search)",
        "Accept": "application/sparql-results+json",
    })
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())

    rows = data["results"]["bindings"]
    print(f"wikidata rows (pre-aggregation): {len(rows)}")

    # aggregate by qid
    from collections import defaultdict
    agg: dict[str, dict] = defaultdict(lambda: {"en": "", "hi": "", "aliases_hi": set(), "aliases_en": set()})
    for b in rows:
        qid = b.get("item", {}).get("value", "").rsplit("/", 1)[-1]
        if not qid:
            continue
        en = b.get("itemLabel", {}).get("value", "").strip()
        hi = b.get("itemLabel_hi", {}).get("value", "").strip()
        al_hi = b.get("alias_hi", {}).get("value", "").strip()
        al_en = b.get("alias_en", {}).get("value", "").strip()
        if en and not agg[qid]["en"]:
            agg[qid]["en"] = en
        if hi:
            agg[qid]["hi"] = hi
        if al_hi:
            agg[qid]["aliases_hi"].add(al_hi)
        if al_en:
            agg[qid]["aliases_en"].add(al_en)

    n_with_hi = 0
    with OUT.open("w") as f:
        for qid, d in sorted(agg.items()):
            if d["hi"] or d["aliases_hi"]:
                n_with_hi += 1
            f.write(json.dumps({
                "qid": qid,
                "english_label": d["en"],
                "hindi_label": d["hi"],
                "aliases_hi": sorted(d["aliases_hi"]),
                "aliases_en": sorted(d["aliases_en"]),
            }, ensure_ascii=False) + "\n")
    print(f"wrote {len(agg)} unique items -> {OUT}")
    print(f"  with Hindi label or alias: {n_with_hi}")


if __name__ == "__main__":
    main()
