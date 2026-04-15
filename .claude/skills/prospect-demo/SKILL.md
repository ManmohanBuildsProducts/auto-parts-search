---
name: prospect-demo
description: Prepare a concierge demo for an auto-parts prospect. Takes their catalog file (CSV/Excel/JSON/JSONL/folder/URL) and a slug, ensures local services are running, ingests via scripts/prepare_demo.py, and returns a public shareable URL. Use when the user says anything like "set up a demo for <X>", "ingest this catalog", "prospect demo", "new demo", or invokes /demo.
---

# Prospect Demo Skill

End-to-end automation for the concierge demo loop documented in
`docs/CONCIERGE_DEMO.md`. Removes the need for the user to remember the
command sequence.

## When to invoke this skill

Trigger if the user says any of:

- "Set up a demo for Pikpart" / "...for <company>"
- "Ingest this catalog" / "Ingest <file>"
- "Prospect demo" / "new demo" / "/demo"
- "I got a catalog from <X>, make a demo"
- "Run the CLI on this file"
- Any request to process a CSV/Excel/JSON/JSONL of auto-parts for a demo

## What to do

### Step 1 — Gather inputs from the user
Ask for what you're missing, in this order (use AskUserQuestion or
plain prompts):

1. **Source** — what's the input?
   - File path (CSV, XLSX, XLS, JSON, JSONL)
   - Folder path (many files, same schema)
   - HTTP URL (JSONL)
2. **Slug** — URL-safe short name (e.g. `pikpart`, `autodukan`, `parts-big-boss`). Lowercase, hyphen-separated. This becomes the demo URL suffix.
3. **Display name** (optional) — defaults to the slug. Shown in the demo UI header.

Accept abbreviated input and confirm back before proceeding.

### Step 2 — Verify services are up

Run:
```bash
curl -sf http://127.0.0.1:7700/health && echo "meili OK"
curl -sf http://127.0.0.1:8000/health && echo "api OK"
pgrep -f "cloudflared tunnel" >/dev/null && echo "tunnel OK"
```

If anything is down, run the helper:
```bash
bash scripts/start_all.sh
```

Wait for it to print the public URL. Capture that URL for step 4.

### Step 3 — Run the ingestion CLI

```bash
python3.11 -m scripts.prepare_demo \
    --file "<abs_path>" \
    --slug "<slug>" \
    --name "<name>" \
    --no-confirm
```

Swap `--file` with `--folder` or `--url` as appropriate.

If column auto-detection looks wrong in the output, re-run without
`--no-confirm` (interactive) OR add an explicit `--map` flag like:
`--map "Product Name=name,SKU=id,Mfg=brand"`.

The CLI prints:
```
✅ Demo ready
   Session ID: <slug>
   Try page:   http://127.0.0.1:8000/demo/<slug>/try
```

### Step 4 — Format the shareable URL

Take the public Cloudflare tunnel URL captured in step 2 and replace
the `http://127.0.0.1:8000` prefix in the printed Try page URL.

Example output to present to the user:

```
🎯 Demo ready for Pikpart

Share this URL with the prospect:
  https://<tunnel-sub>.trycloudflare.com/demo/pikpart/try

Good queries to suggest they try:
  - "brake pad Swift"   (baseline English)
  - "brek pad swift"    (typo tolerance)
  - "patti badal do"    (Hindi slang)
  - "ब्रेक पैड"            (Devanagari)
  - "<their part #>"    (exact SKU)
  - "engine garam"      (symptom)

Session isolated, auto-expires in 24h, re-run this skill with the
same slug to refresh.
```

### Step 5 — (Optional) troubleshooting

- **CLI failed with `could not decode <file>`** → ask user to re-save the file as UTF-8 CSV
- **`v3 corpus cache missing`** → run `python3.11 -m auto_parts_search.search_hybrid build-cache`
- **CLI stuck on "uploading async"** → normal for >10K products. Extract job ID from output, poll:
  `curl -s http://127.0.0.1:8000/demo/catalog/<jid> | python3 -m json.tool`
- **Cloudflare tunnel URL changed** → re-grep `/tmp/cf/tunnel.log`

## Do NOT

- Do NOT edit code, ADRs, or notebooks while running this skill unless
  the user asks. This is an ops/demo skill, not a development skill.
- Do NOT skip the service health check in Step 2. If Meilisearch or
  the API is down, the CLI will fail halfway and confuse the user.
- Do NOT assume the file path — always confirm it exists with `ls -la`
  before passing to the CLI.

## Example session

User: `/demo set up pikpart from ~/Downloads/pikpart_catalog.xlsx`

Assistant response (summarized):
1. "Checking services…" (runs curl pings; if any fail, runs `scripts/start_all.sh`)
2. "Running `scripts/prepare_demo.py --file ~/Downloads/pikpart_catalog.xlsx --slug pikpart --name Pikpart --no-confirm`"
3. Reads CLI output, captures session ID
4. "Here's your shareable URL: `https://<tunnel>.trycloudflare.com/demo/pikpart/try`"
5. Lists good demo queries

## Related files

- `docs/CONCIERGE_DEMO.md` — full playbook with troubleshooting
- `scripts/prepare_demo.py` — the CLI this skill wraps
- `scripts/start_all.sh` — service-boot helper
- `auto_parts_search/static/try.html` — the UI the prospect will see
