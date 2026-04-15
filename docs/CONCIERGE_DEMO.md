# Concierge demo playbook

The operational runbook for "prospect sends catalog → you send demo URL" in minutes.

**TL;DR** (once everything's running):
```bash
python3.11 -m scripts.prepare_demo \
    --file ~/Downloads/<prospect_catalog_file> \
    --slug <prospect_name> \
    --name "<Prospect Display Name>"
```
Share the printed **Try page URL** with them.

---

## 0. What prospects will send you

| They send | You receive | Handled |
|---|---|---|
| CSV exported from their admin | `catalog.csv` | ✅ pass to `--file` |
| Excel export | `catalog.xlsx` / `.xls` | ✅ pass to `--file` |
| Multi-sheet Excel | (concat or pick sheet manually) | Manually save each sheet as CSV, then use `--folder` |
| Shopify `products.json` export | `products.json` | ✅ auto-detects `{"products":[...]}` shape |
| Folder with split files | `catalog/*.csv` | ✅ use `--folder catalog/` |
| URL to their JSONL | `https://...export.jsonl` | ✅ use `--url` (server pulls) |
| Google Drive / Dropbox link | (download first) | Download, then `--file` |
| WhatsApp-forwarded image of a PDF | laughs in pre-revenue | Ask for CSV/Excel instead |

---

## 1. One-time setup (first session after reboot)

Three services must be running on the local Mac. A minute of setup; survives as long as you don't reboot.

### 1a. Start Meilisearch
```bash
cd /Users/mac/Projects/auto-parts-search
MEILI_NO_ANALYTICS=true meilisearch \
  --db-path data/meili/data.ms \
  --env development \
  --master-key aps_local_dev_key_do_not_use_in_prod \
  --no-analytics \
  --http-addr 127.0.0.1:7700 \
  > data/meili/meili.log 2>&1 &
```
Verify: `curl -s http://127.0.0.1:7700/health` should return `{"status":"available"}`.

### 1b. Start the API
```bash
cd /Users/mac/Projects/auto-parts-search
python3.11 -m uvicorn auto_parts_search.api:app --port 8000 --log-level warning > /tmp/api.log 2>&1 &
# wait ~12 sec for v3 embedding model to load
sleep 14
curl -s http://127.0.0.1:8000/health
# should return: {"status":"ok","meilisearch":true,"v3_cache":true,"bridges":true}
```

### 1c. Start the Cloudflare Tunnel
```bash
cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/cf/tunnel.log 2>&1 &
# wait, then extract URL:
sleep 6
grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf/tunnel.log | head -1
```
That URL is the public base — replaces `http://127.0.0.1:8000` when sharing with prospects.

**Save that URL somewhere you can find** (it changes on every tunnel restart).

---

## 2. Prepare a prospect demo (the loop)

**Scenario:** prospect emailed you `pikpart_export.xlsx`.

```bash
cd /Users/mac/Projects/auto-parts-search
python3.11 -m scripts.prepare_demo \
    --file ~/Downloads/pikpart_export.xlsx \
    --slug pikpart \
    --name "Pikpart"
```

### What happens
1. CLI reads the file (CSV / Excel / JSON / JSONL — auto-detects)
2. Shows column auto-detection:
   ```
   auto-detected mapping:
     name            <- Product Name
     id              <- SKU Code
     brand           <- Manufacturer
     vehicle_model   <- Car Model
   ```
3. Interactive confirm (press Enter for y, or type a replacement column name)
4. Skip interactive with `--no-confirm` + `--map "YourCol=name,Other=brand"`
5. Uploads (sync if ≤10K products, async batched if larger)
6. Prints:
   ```
   ✅ Demo ready
      Session ID: pikpart
      Try page:   http://127.0.0.1:8000/demo/pikpart/try
   ```

### Share the URL (using the public tunnel base)
Replace the localhost base with your Cloudflare tunnel URL:

```
https://<tunnel-subdomain>.trycloudflare.com/demo/pikpart/try
```

Copy that, paste into WhatsApp / email / DM. **That is the demo.**

---

## 3. What the prospect sees

A dark-themed single-page search app:
- Their catalog name in the header
- Count of products indexed
- Search box (debounced autosearch as they type)
- Example queries they can click
- Per-hit card: name · brand · vehicle · part numbers · fused score
- Query-class badge (exact_english / hindi_hinglish / symptom / part_number)
- Latency (usually 50-150ms warm)

---

## 4. Demo script (what to tell prospects)

> "I've loaded your catalog into our search API. Try it here: `https://.../demo/<slug>/try`. Type any query your customers might type — in English, Hindi, Hinglish, with typos, or by part number. Results come in under 150ms. Your catalog is isolated; nobody else sees it. The URL expires in 24h unless we pin it."

**Good demo queries to suggest, given Indian auto-parts prospects:**
- `brake pad Swift` — baseline exact English
- `brek pad swift` — typo tolerance
- `patti badal do bhaiya` — Hindi slang for "change the brake pad, brother"
- `ब्रेक पैड` — Devanagari input
- `<one of their actual part numbers>` — direct SKU lookup
- `<one of their real brand names>` — brand-as-generic query
- `engine garam ho raha hai` — symptom query

---

## 5. Common edge cases

| Problem | Fix |
|---|---|
| Column auto-detect misses a field | Run with `--map "YourCol=name,Other=brand"` to set explicitly |
| "could not decode" on weird CSV | Open in Excel → save as UTF-8 CSV → retry |
| Upload slow for >10K products | Normal — single-shot hits 10K cap. CLI auto-switches to async batched. Poll progress in the log. |
| Prospect sends a Google Sheet URL | Export as CSV (File → Download → CSV), then `--file` |
| Cloudflare URL changed | Grep the log again, update the message to the prospect |
| API returns `v3 corpus cache missing` | Run `python3 -m auto_parts_search.search_hybrid build-cache` once |
| Everything died after Mac reboot | Re-run steps 1a/1b/1c |

---

## 6. Limitations to know (and tell prospects honestly)

- **Trycloudflare URL changes** on every tunnel restart. Named tunnel fixes this (30 min setup, free, requires Cloudflare DNS).
- **URL is unauthenticated** — anyone with the link can search. Fine for private demo links; not for public landing pages.
- **Max 500K products per demo session** (memory cap on CPU).
- **Sessions auto-expire in 24h.** Re-run the CLI with the same `--slug` to refresh.
- **Mac must stay awake.** Disable sleep via `caffeinate -d -i` while you're live-demo'ing, or move to Hetzner.

---

## 7. Phase 2 — when a prospect says "yes, let's pilot"

Upgrade triggers:
1. **Named Cloudflare tunnel** — permanent URL like `search.yourdomain.com` (~30 min)
2. **Hetzner deploy** — so Mac can sleep (~2 hr, €3.29/mo)
3. **API key auth per tenant** — prevents URL-sharing abuse (~2 hr)
4. **Real DB connector or webhook** — if they want recurring sync (~1-2 days)
5. **Embed on GPU** — for >500K-SKU customers (Modal / Colab) (~1 day integration)

---

## 8. Fast paths (copy-paste ready)

### Restart everything after reboot
```bash
cd /Users/mac/Projects/auto-parts-search
./scripts/start_all.sh     # (optional helper; see below)
```

### Check everything's up
```bash
curl -s http://127.0.0.1:7700/health
curl -s http://127.0.0.1:8000/health
pgrep -f cloudflared && echo "tunnel running" || echo "tunnel DOWN"
```

### Full-send: new prospect in 60 seconds
```bash
python3.11 -m scripts.prepare_demo \
    --file ~/Downloads/<theirfile> \
    --slug <theirname> \
    --name "<Their Display Name>" \
    --no-confirm     # skip prompts when columns auto-detect cleanly
```

### Kill + restart the tunnel (new URL)
```bash
pkill -f cloudflared
cloudflared tunnel --url http://localhost:8000 --no-autoupdate > /tmp/cf/tunnel.log 2>&1 &
sleep 6
grep -oE "https://[a-z0-9-]+\.trycloudflare\.com" /tmp/cf/tunnel.log | head -1
```
