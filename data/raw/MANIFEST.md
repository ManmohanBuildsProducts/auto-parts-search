# Raw Data Manifest

Ground truth for `data/raw/`. Scraped jsonl too large to commit (~500MB); snapshots uploaded to Hugging Face Datasets and referenced here.

**Rule:** every entry in `data/training/golden/METADATA.md` must reference a raw snapshot in this manifest.

**Fetch:** `bash scripts/fetch_raw.sh` downloads the latest reference snapshot and verifies SHA.

---

## Snapshots

### scrape-v3 (2026-04-13)

**Status:** reference — current blessed raw snapshot. Used to produce `data/training/golden/`.
**Storage:** Hugging Face Datasets (private)
**Tarball URL:** https://huggingface.co/datasets/ManmohanBuildsProducts/auto-parts-search-raw/resolve/main/scrape-v3-2026-04-13.tar.gz
**Tarball SHA256:** `a7bf97525c4bd54b6f20369e85715cd2c724cdd4943a7b9ea07a58da2af25bfa`
**Tarball size:** 21 MB (compressed from ~516 MB uncompressed — jsonl of URLs compresses ~24× via gzip)

**Contents:**

| File | Rows | SHA256 | Notes |
|------|------|--------|-------|
| `shopify_products.jsonl` | 24,865 | `4a2edeb94a5980b22f34017b7cf32409fc4716b191d974d86c5742f2cb3e0861` | SparesHub (12,500 Skoda) + Bikespares.in (5,700 2W) + eAuto (6,600 2W) via public `/products.json` endpoints |
| `playwright_products.jsonl` | 479 | `c7d32cfe7d00cdbf3d01eca319d520f79600454a6ea753c9d178a638f9ead6ce` | Boodmo + Autozilla browser-rendered scrape |
| `boodmo_sitemap_products.jsonl` | 1,407,638 | `1a23db3e2be559bcdb26d50b3b0ad275583965c90af18750fb8a275964e83e83` | Boodmo sitemap XML parse — part URLs only, no vehicle info |
| `additional_products.jsonl` | 608 | `dadaa2d3499a8544fbe168e91fadbad06aea89bb7a2fb03fb9c317e986202186` | Supplementary products (SparesHub missing pages + manual additions) |

Total: 1,433,590 product rows across 4 files.

**Originating scrape dates:** Shopify + Playwright Apr 9, 2026; Boodmo sitemap Apr 9, 2026.

### scrape-v1 + scrape-v2 (retroactively: never uploaded)

Earlier manifest revisions referenced `scrape-v1` as a placeholder before the HF pipeline existed. No tarball was produced for v1 or v2; `scrape-v3` is the first real snapshot. Numbering starts from v3 in git history for continuity — future uploads continue v4, v5, etc.

---

## Schema (for future snapshots)

Each snapshot section must include:
- Snapshot name (e.g. `scrape-v4-2026-07-01`)
- Status (`reference` = used by a promoted golden model, `experimental`, `deprecated`)
- Tarball URL + SHA256 + size
- Per-file row count + SHA256
- Scrape dates + any drift notes vs prior snapshot

## Fetching

```bash
# Latest reference snapshot
bash scripts/fetch_raw.sh

# Specific snapshot (e.g. to reproduce an older model run)
bash scripts/fetch_raw.sh scrape-v3-2026-04-13
```

## Creating a new snapshot

```bash
# After a fresh scrape
bash scripts/snapshot_to_hf.sh
# Then manually append the new entry to this file and commit
```
