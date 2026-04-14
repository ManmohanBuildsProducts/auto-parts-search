"""Meilisearch BM25 index + search for auto-parts KG corpus.

Companion to `auto_parts_search.tokenizer`. Builds a searchable index
from the KG's part nodes, using IndicTokenizer for dual-script expansion.

Index schema (one doc per part):
  id              str    # part node id, e.g. "part:ac_compressor"
  name            str    # canonical English name
  aliases         list[str]  # all known_as aliases (Roman + Devanagari)
  system          str    # parent system name
  indexed_tokens  list[str]  # pre-expanded dual-script tokens

Query path:
  raw user query
  -> IndicTokenizer.query_tokens() (dual-script expansion)
  -> join on whitespace -> send as q to Meilisearch
  -> Meilisearch applies BM25 saliency + typo tolerance

Usage:
  python3 -m auto_parts_search.search_bm25 ingest
  python3 -m auto_parts_search.search_bm25 search "patti badal do bhaiya"
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from auto_parts_search.tokenizer import IndicTokenizer, SarvamTransliterator, BridgeTransliterator

MEILI_URL = os.environ.get("MEILI_URL", "http://127.0.0.1:7700")
MEILI_KEY = os.environ.get("MEILI_KEY", "aps_local_dev_key_do_not_use_in_prod")
INDEX_NAME = "parts"
GRAPH_DB = Path("data/knowledge_graph/graph.db")


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {MEILI_KEY}", "Content-Type": "application/json"}


def _meili(method: str, path: str, body: Any = None) -> dict:
    url = f"{MEILI_URL}{path}"
    r = requests.request(method, url, headers=_headers(), json=body, timeout=60)
    r.raise_for_status()
    if r.content:
        return r.json()
    return {}


# ---------- ingest ----------

def load_kg_docs(db_path: Path = GRAPH_DB) -> list[dict]:
    """One doc per part. Pulls aliases + parent system."""
    conn = sqlite3.connect(db_path)

    # Part id -> name
    parts: dict[str, str] = {}
    for pid, name in conn.execute("SELECT id, name FROM nodes WHERE type='part'"):
        parts[pid] = name

    # Aliases (alias node -> part)
    aliases: dict[str, list[str]] = defaultdict(list)
    for alias_name, part_id in conn.execute(
        "SELECT n.name, e.dst FROM edges e JOIN nodes n ON n.id = e.src "
        "WHERE e.type='known_as' AND n.type='alias'"
    ):
        aliases[part_id].append(alias_name)

    # Parent systems
    systems: dict[str, list[str]] = defaultdict(list)
    for part_id, sys_name in conn.execute(
        "SELECT e.src, n.name FROM edges e JOIN nodes n ON n.id = e.dst "
        "WHERE e.type='in_system' AND n.type='system'"
    ):
        systems[part_id].append(sys_name)

    conn.close()

    docs: list[dict] = []
    skipped_noise = 0
    for pid, name in parts.items():
        # Skip HSN-taxonomy concat names — they clutter results without aiding search
        # (e.g. "Parts and accessories of the motor vehicles...:*Suspension systems...")
        if ":" in name or len(name) > 80:
            skipped_noise += 1
            continue
        als = aliases.get(pid, [])
        sys_names = systems.get(pid, [])
        docs.append({
            "id": pid.replace(":", "_"),  # Meilisearch forbids ':' in doc id
            "part_id": pid,
            "name": name,
            "aliases": als,
            "system": ", ".join(sys_names) if sys_names else "",
        })
    print(f"  [load] {len(docs)} indexed, {skipped_noise} HSN-noise docs skipped")
    return docs


def expand_tokens(docs: list[dict], tokenizer: IndicTokenizer) -> list[dict]:
    """Add `indexed_tokens` via IndicTokenizer.index_tokens over name + aliases + system."""
    for d in docs:
        blob = " ".join(filter(None, [d["name"], " ".join(d["aliases"]), d["system"]]))
        d["indexed_tokens"] = tokenizer.index_tokens(blob)
    return docs


def ingest(tokenizer: IndicTokenizer | None = None) -> None:
    tok = tokenizer or IndicTokenizer()
    docs = load_kg_docs()
    docs = expand_tokens(docs, tok)
    print(f"prepared {len(docs)} KG part docs")

    # Create/clear index
    try:
        _meili("DELETE", f"/indexes/{INDEX_NAME}")
    except requests.HTTPError:
        pass

    _meili("POST", "/indexes", {"uid": INDEX_NAME, "primaryKey": "id"})

    # Configure searchable attributes — order matters for relevance
    _meili("PATCH", f"/indexes/{INDEX_NAME}/settings", {
        "searchableAttributes": ["name", "aliases", "indexed_tokens", "system"],
        "displayedAttributes": ["id", "part_id", "name", "aliases", "system"],
        "typoTolerance": {"enabled": True, "minWordSizeForTypos": {"oneTypo": 4, "twoTypos": 7}},
        "rankingRules": ["words", "typo", "proximity", "attribute", "sort", "exactness"],
    })

    # Push docs in one batch (small corpus)
    task = _meili("POST", f"/indexes/{INDEX_NAME}/documents", docs)
    print(f"enqueued task: {task}")

    # Wait for index to finish
    import time
    for _ in range(60):
        t = _meili("GET", f"/tasks/{task['taskUid']}")
        if t["status"] == "succeeded":
            print(f"indexed in {t.get('duration', 'n/a')}")
            return
        if t["status"] == "failed":
            raise RuntimeError(f"indexing failed: {t}")
        time.sleep(0.5)
    raise RuntimeError("indexing timed out")


# ---------- search ----------

@dataclass
class Bm25SearchHit:
    part_id: str
    name: str
    aliases: list[str]
    system: str
    _raw: dict


def search(query: str, k: int = 20, tokenizer: IndicTokenizer | None = None) -> list[Bm25SearchHit]:
    tok = tokenizer or IndicTokenizer()
    expanded = tok.query_tokens(query)
    # Build expansion string; Meilisearch's `last` strategy drops right-most tokens
    # until a match is found. Put the raw user query FIRST so it's the last to be dropped.
    q_str = " ".join(expanded)
    resp = _meili("POST", f"/indexes/{INDEX_NAME}/search", {
        "q": q_str,
        "limit": k,
        "showRankingScore": True,
        "matchingStrategy": "frequency",   # rarer terms kept; plays well with typo tolerance
    })
    hits = []
    for h in resp.get("hits", []):
        hits.append(Bm25SearchHit(
            part_id=h.get("part_id", h["id"]),
            name=h["name"],
            aliases=h.get("aliases", []),
            system=h.get("system", ""),
            _raw=h,
        ))
    return hits


# ---------- CLI ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ingest", "search", "stats"])
    ap.add_argument("query", nargs="?", default=None)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--sarvam", action="store_true", help="Enable Sarvam fallback for tokenizer")
    args = ap.parse_args()

    tok_kwargs = {}
    if args.sarvam:
        tok_kwargs["transliterator"] = BridgeTransliterator(sarvam=SarvamTransliterator())
    tok = IndicTokenizer(**tok_kwargs)

    if args.cmd == "ingest":
        ingest(tok)
    elif args.cmd == "search":
        if not args.query:
            print("usage: search '<query>'", file=sys.stderr)
            sys.exit(1)
        hits = search(args.query, k=args.k, tokenizer=tok)
        for i, h in enumerate(hits, 1):
            score = h._raw.get("_rankingScore", 0)
            print(f"{i:2d}  [{score:.3f}]  {h.name}")
            if h.aliases:
                print(f"        aliases: {', '.join(h.aliases[:4])}")
            if h.system:
                print(f"        system:  {h.system}")
    elif args.cmd == "stats":
        s = _meili("GET", f"/indexes/{INDEX_NAME}/stats")
        print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
