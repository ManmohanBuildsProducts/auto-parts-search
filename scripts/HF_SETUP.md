# Hugging Face Datasets — raw-data snapshot setup

**Purpose:** host `data/raw/` (scraped product catalogs, gitignored, a few hundred MB) on Hugging Face as a versioned private dataset. Free at this scale. Satisfies ADR 009 reproducibility.

**Why HF over Backblaze B2 / S3 / R2:** same free tier at our size, but HF is purpose-built for versioned datasets with git-LFS under the hood, a clean web UI for browsing, and a credibility signal for prospect conversations ("dataset hosted on Hugging Face"). Zero egress cost from the CLI.

---

## One-time setup (5 min, your action)

### 1. Create a Hugging Face account
Go to <https://huggingface.co/join>. Free. Email + username + password.

### 2. Create an access token
- Go to <https://huggingface.co/settings/tokens>.
- Click **New token**.
- Name: `auto-parts-search-write`.
- Role: **Write** (needed to create + upload to datasets).
- Copy the `hf_...` token.

### 3. Install the CLI on this machine
```bash
pip3 install --user huggingface_hub
```

### 4. Log in (stores the token locally in `~/.cache/huggingface/token`)
```bash
huggingface-cli login
# paste the hf_... token when prompted
# answer "n" when asked to add token to git credential helper (we don't want it in git)
```

### 5. Tell me your HF username
Once done, reply with your HF username. I'll fill in `scripts/snapshot_to_hf.sh` and `data/raw/MANIFEST.md` with the exact dataset URL (`<username>/auto-parts-search-raw`).

---

## Per-snapshot workflow (what happens for each new scrape)

Run from the repo root:

```bash
bash scripts/snapshot_to_hf.sh
```

The script (to be finalized after step 5 above):
1. Creates a tarball `data/raw/scrape-v<N>-<date>.tar.gz`.
2. Computes SHA256 of each jsonl + the tarball.
3. Uploads to `<username>/auto-parts-search-raw` (private by default).
4. Appends an entry to `data/raw/MANIFEST.md` with the HF URL + SHA256 + row counts.
5. Commits the MANIFEST.md change (the tarball itself stays gitignored).

Fetch on a fresh clone:
```bash
bash scripts/fetch_raw.sh          # reads MANIFEST.md, downloads latest, verifies SHA
```

---

## Why "private by default"

The scraped catalog data includes third-party product listings (Boodmo, Shopify stores) whose ToS ambiguity is noted in `memory/learnings.md`. A private dataset means:
- Only you + collaborators you invite can download.
- HF won't index or embed your URLs in their public search.
- You can flip to public later if a compliance review clears it.

Public would work technically but is not the default recommended path for this repo.

---

## Cost at our scale

| Resource | Our usage (est.) | Free tier | Monthly cost |
|----------|------------------|-----------|--------------|
| Storage | ~500 MB initially, ~5 GB at full scrape scale | Unlimited for public + generous for private | $0 |
| Egress | A few GB/month at pilot stage | Unlimited via CLI | $0 |
| Bandwidth from Datasets API | Minimal | Generous | $0 |

Hugging Face is free at this scale for the foreseeable future.
