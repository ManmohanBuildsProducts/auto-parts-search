"""Concierge ingestion CLI — drop a prospect's catalog file in,
get a shareable demo URL out.

Accepts CSV, Excel (.xlsx/.xls), JSON (array), JSONL, Shopify products.json,
or a folder of any of the above. Auto-detects columns via fuzzy match;
prompts for ambiguous mappings; uploads via the API; prints a URL.

Usage:
    # simplest
    python3 -m scripts.prepare_demo --file ~/Downloads/pikpart.xlsx --slug pikpart

    # folder of multiple files, same schema
    python3 -m scripts.prepare_demo --folder ~/Downloads/autodukan_catalog/ --slug autodukan

    # explicit column map (skips prompts)
    python3 -m scripts.prepare_demo --file x.csv --slug foo \\
        --map "Product Name=name,SKU=id,Mfg=brand,Vehicle=vehicle_model"

    # sample only (speed, skip full embedding)
    python3 -m scripts.prepare_demo --file big.csv --slug test --sample 1000
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

API_BASE = "http://127.0.0.1:8000"
PUBLIC_BASE_DEFAULT = None  # set via --public-url or auto-detected from tunnel

# Fuzzy column name -> our schema field
FIELD_ALIASES: dict[str, list[str]] = {
    "name": [
        "name", "product_name", "product name", "title", "productname",
        "item", "item_name", "item name", "description_title", "product_title",
    ],
    "id": [
        "id", "sku", "product_id", "product id", "productid", "item_code",
        "itemcode", "part_code", "partcode", "partno", "part_no", "part_number",
        "part number", "mpn",
    ],
    "brand": [
        "brand", "brand_name", "brandname", "manufacturer", "mfg", "mfr",
        "make_brand", "brand_make", "brand_manufacturer",
    ],
    "vehicle_make": [
        "vehicle_make", "vehicle make", "vehicleman", "car_brand", "car brand",
        "oem", "oem_brand", "make", "car_make", "fitment_make",
    ],
    "vehicle_model": [
        "vehicle_model", "vehicle model", "model", "car_model", "fitment_model",
        "car_name", "car",
    ],
    "description": [
        "description", "desc", "details", "notes", "short_description",
        "long_description", "product_description", "subtitle",
    ],
}


def _norm_col(name: str) -> str:
    return "".join(c for c in name.lower().strip() if c.isalnum() or c == "_")


def autodetect_columns(columns: list[str]) -> dict[str, str]:
    """Return {our_field: source_column}. Best-effort; empty if ambiguous."""
    chosen: dict[str, str] = {}
    used_src: set[str] = set()
    norm_cols = [(c, _norm_col(c)) for c in columns]

    for field, aliases in FIELD_ALIASES.items():
        alias_norms = [_norm_col(a) for a in aliases]
        # exact match first
        for orig, nrm in norm_cols:
            if orig in used_src:
                continue
            if nrm in alias_norms:
                chosen[field] = orig
                used_src.add(orig)
                break
        if field in chosen:
            continue
        # partial match (nrm contains an alias)
        for orig, nrm in norm_cols:
            if orig in used_src:
                continue
            if any(a in nrm for a in alias_norms):
                chosen[field] = orig
                used_src.add(orig)
                break
    return chosen


def prompt_confirm_map(columns: list[str], auto: dict[str, str]) -> dict[str, str]:
    print("\n=== Column mapping ===")
    for field in FIELD_ALIASES.keys():
        src = auto.get(field)
        if src:
            resp = input(f"  {field:15s} <- {src}   [y/n/change]: ").strip().lower()
            if resp == "y" or resp == "":
                pass
            elif resp == "n":
                auto.pop(field, None)
            else:  # treat input as replacement col name
                auto[field] = resp
        else:
            print(f"  {field:15s} <- (no match)   columns: {columns}")
            resp = input(f"     map {field}? (enter column name or blank to skip): ").strip()
            if resp:
                auto[field] = resp
    return auto


def parse_map_flag(s: str) -> dict[str, str]:
    # "Source=target,Source2=target2"
    out = {}
    for pair in s.split(","):
        pair = pair.strip()
        if "=" not in pair:
            continue
        src, tgt = pair.split("=", 1)
        out[tgt.strip()] = src.strip()   # user provides "source=target"; we invert to field->source
    return out


def read_file(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".csv", ".tsv", ".txt"):
        # try a few common encodings
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                return pd.read_csv(path, encoding=enc, sep=None, engine="python",
                                    dtype=str, keep_default_na=False, on_bad_lines="skip")
            except UnicodeDecodeError:
                continue
        raise ValueError(f"could not decode {path}")
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str, keep_default_na=False)
    if suffix == ".jsonl" or path.name.endswith(".jsonl"):
        records = []
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            records.append(json.loads(line))
        return pd.DataFrame(records, dtype=str)
    if suffix == ".json":
        data = json.loads(path.read_text())
        # Shopify products.json shape
        if isinstance(data, dict) and "products" in data:
            return pd.DataFrame(data["products"], dtype=str)
        if isinstance(data, list):
            return pd.DataFrame(data, dtype=str)
        raise ValueError(f"unsupported JSON shape in {path}")
    raise ValueError(f"unknown format: {path.suffix}")


def read_folder(folder: Path) -> pd.DataFrame:
    frames = []
    for p in sorted(folder.iterdir()):
        if p.suffix.lower() in (".csv", ".tsv", ".xlsx", ".xls", ".json", ".jsonl"):
            try:
                frames.append(read_file(p))
                print(f"  [+] {p.name}: {len(frames[-1])} rows")
            except Exception as e:
                print(f"  [!] {p.name}: skip ({e})")
    if not frames:
        raise ValueError(f"no readable files in {folder}")
    # outer-concat: preserve all columns even if some files are missing them
    return pd.concat(frames, ignore_index=True, sort=False).fillna("")


def df_to_products(df: pd.DataFrame, mapping: dict[str, str]) -> list[dict]:
    out = []
    for _, row in df.iterrows():
        p = {}
        for field, src_col in mapping.items():
            if src_col in df.columns:
                val = str(row[src_col]).strip()
                if val:
                    p[field] = val
        if p.get("name"):
            out.append(p)
    return out


def upload_sync(api_base: str, slug: str, name: str, products: list[dict]) -> dict:
    r = requests.post(
        f"{api_base}/demo/catalog",
        json={"name": name, "slug": slug, "products": products},
        timeout=1800,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"{r.status_code}: {r.text[:500]}")
    d = r.json()
    return {"session_id": d["session_id"], "api_key": d.get("api_key"),
            "embedding_seconds": d.get("embedding_seconds")}


def upload_async(api_base: str, slug: str, name: str, products: list[dict], chunk: int = 5000) -> dict:
    r = requests.post(f"{api_base}/demo/catalog/start",
                      json={"name": name, "slug": slug}, timeout=60)
    r.raise_for_status()
    start_resp = r.json()
    jid = start_resp["job_id"]
    api_key = start_resp.get("api_key")
    print(f"  [job] {jid}  staging {len(products)} products in chunks of {chunk}...")
    for i in range(0, len(products), chunk):
        batch = products[i : i + chunk]
        rr = requests.post(f"{api_base}/demo/catalog/{jid}/batch",
                           json={"products": batch}, timeout=120)
        rr.raise_for_status()
        print(f"    batch {i//chunk + 1}: staged {rr.json()['n_staged']}")
    r = requests.post(f"{api_base}/demo/catalog/{jid}/commit", timeout=60)
    r.raise_for_status()
    print(f"  [job] committed, embedding...")
    # poll
    last_pct = -1.0
    while True:
        s = requests.get(f"{api_base}/demo/catalog/{jid}", timeout=30).json()
        pct = s.get("progress_pct") or 0.0
        if pct != last_pct:
            print(f"    {s['status']}: {s['n_embedded']}/{s['n_total']}  ({pct}%)")
            last_pct = pct
        if s["status"] in ("ready", "failed"):
            break
        time.sleep(3)
    if s["status"] != "ready":
        raise RuntimeError(f"job failed: {s.get('error')}")
    return {"session_id": s["session_id"], "api_key": api_key,
            "search_url": s["search_url"]}


def main() -> None:
    ap = argparse.ArgumentParser(description="Concierge ingest: catalog file -> demo URL")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--file", type=Path, help="single CSV/XLSX/JSON/JSONL")
    src.add_argument("--folder", type=Path, help="folder of catalog files")
    src.add_argument("--url", help="HTTP(S) URL of JSONL catalog")
    ap.add_argument("--slug", required=True, help="URL slug, e.g. 'pikpart'")
    ap.add_argument("--name", default=None, help="display name (defaults to slug)")
    ap.add_argument("--map", default=None, help='explicit column map "Source=target,..."')
    ap.add_argument("--sample", type=int, default=None, help="sample first N rows only")
    ap.add_argument("--no-confirm", action="store_true", help="skip interactive column confirmation")
    ap.add_argument("--api", default=API_BASE, help="API base URL (default: local)")
    ap.add_argument("--public-url", default=None,
                    help="public URL used in the printed link (defaults to --api)")
    args = ap.parse_args()

    # Load
    if args.url:
        print(f"Ingesting from URL: {args.url}")
        r = requests.post(
            f"{args.api}/demo/catalog/ingest-url",
            json={"name": args.name or args.slug, "slug": args.slug, "source_url": args.url},
            timeout=60,
        )
        r.raise_for_status()
        jid = r.json()["job_id"]
        print(f"  [job] {jid}  server is fetching + embedding; poll /demo/catalog/{jid}")
        while True:
            s = requests.get(f"{args.api}/demo/catalog/{jid}", timeout=30).json()
            print(f"    {s['status']}: staged={s['n_staged']} embedded={s['n_embedded']} pct={s.get('progress_pct')}")
            if s["status"] in ("ready", "failed"):
                break
            time.sleep(5)
        if s["status"] != "ready":
            sys.exit(f"job failed: {s.get('error')}")
        sid = s["session_id"]
    else:
        print(f"Reading {args.file or args.folder}...")
        if args.file:
            df = read_file(args.file)
        else:
            df = read_folder(args.folder)
        print(f"  loaded {len(df)} rows, columns: {list(df.columns)[:8]}{' ...' if len(df.columns) > 8 else ''}")

        if args.sample:
            df = df.head(args.sample)
            print(f"  sampled first {len(df)} rows")

        mapping = autodetect_columns(list(df.columns))
        print(f"\n  auto-detected mapping:")
        for k, v in mapping.items():
            print(f"    {k:15s} <- {v}")

        if args.map:
            mapping.update(parse_map_flag(args.map))
        elif not args.no_confirm and sys.stdin.isatty():
            mapping = prompt_confirm_map(list(df.columns), mapping)

        if "name" not in mapping:
            sys.exit("ERROR: required field 'name' not mapped. Use --map 'YourCol=name'.")

        products = df_to_products(df, mapping)
        print(f"  prepared {len(products)} products (dropped {len(df) - len(products)} rows w/o name)")
        if not products:
            sys.exit("no valid products after mapping")

        # Show first 3 mapped rows
        print(f"\n  preview:")
        for p in products[:3]:
            print(f"    {p}")

        # Choose sync/async based on size
        if len(products) <= 10_000:
            print(f"\n  uploading sync ({len(products)} products)...")
            result = upload_sync(args.api, args.slug, args.name or args.slug, products)
            print(f"    embedded in {result.get('embedding_seconds')}s")
            sid = result["session_id"]
        else:
            print(f"\n  uploading async (large catalog)...")
            result = upload_async(args.api, args.slug, args.name or args.slug, products)
            sid = result["session_id"]

    # Print the shareable URL
    public = args.public_url or args.api
    api_key = None
    if args.url:
        # Fetch key from job status
        st = requests.get(f"{args.api}/demo/catalog/{sid}", timeout=10).json()
        # (key isn't returned in status; retrieve from the start response if we have it)
    else:
        api_key = result.get("api_key")
    print(f"\n{'='*60}")
    print(f"✅ Demo ready")
    print(f"   Session ID: {sid}")
    if api_key:
        print(f"   API Key:    {api_key}")
        print(f"   Search:     {public}/demo/{sid}/search?q=...&key={api_key}")
        print(f"   Try page:   {public}/demo/{sid}/try?key={api_key}")
    else:
        print(f"   Search:     {public}/demo/{sid}/search?q=...")
        print(f"   Try page:   {public}/demo/{sid}/try")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
