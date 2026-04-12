# Raw Data Manifest

This file is the ground truth for `data/raw/`. Scraped data is too large to commit (~hundreds of MB); snapshots are uploaded to cold storage and referenced here.

**Rule:** every entry in `data/training/golden/METADATA.md` must reference a raw snapshot in this manifest.

---

## Snapshots

### scrape-v1 (2026-04-10)

**Status:** reference — used to produce golden-v1 training pairs and benchmark.
**Storage:** pending upload (Backblaze B2 — see T603c).
**Tarball URL:** *TBD (T603c)*
**Tarball SHA256:** *TBD*

**Contents** (per `data/raw/`):

| File | Rows | SHA256 | Notes |
|------|------|--------|-------|
| shopify_products.jsonl | *TBD* | *TBD* | SparesHub + Bikespares + eAuto — from Shopify `/products.json` API |
| playwright_products.jsonl | 479 | *TBD* | Boodmo + Autozilla browser-rendered |
| boodmo_sitemap.jsonl | 1,400,000+ | *TBD* | Boodmo XML sitemap parse — no vehicle info, part names only |

**Fill procedure** (once Backblaze bucket is set up):
```bash
# From project root
cd data/raw
shasum -a 256 *.jsonl > SHA256SUMS.txt
tar czf scrape-v1-2026-04-10.tar.gz *.jsonl SHA256SUMS.txt
shasum -a 256 scrape-v1-2026-04-10.tar.gz
# upload tarball to Backblaze, record URL + SHA256 above
```

---

## Schema

Each snapshot section must include:
- Snapshot name (e.g. `scrape-v2-2026-07-01`)
- Status (`reference` = used by a promoted golden model, `experimental`, `deprecated`)
- Tarball URL + SHA256
- Per-file row count + SHA256
- Scrape date, scrape git commit hash (if scraper was run from committed code)
- Notes on drift vs prior snapshot

## Fetching
```bash
python3 scripts/fetch_raw.py            # downloads the latest reference snapshot
python3 scripts/fetch_raw.py scrape-v1  # specific snapshot
```
