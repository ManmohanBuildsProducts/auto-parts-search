"""Fetch ASDC Qualification Pack PDFs (auto-sector roles) and extract text.

Public government (NSDC-backed) content. Scrapes the job-roles index,
downloads QP PDFs for automobile-sector NSQCs, runs pdftotext, and emits
per-QP Devanagari tokens + surrounding English context.

Usage:
    python3.11 -m scripts.fetch_asdc_qps
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

INDEX_URL = "https://www.asdc.org.in/job-roles"
OUT_DIR = Path("data/external/raw/asdc_qps")
PROCESSED = Path("data/external/processed/asdc_qps.jsonl")

# The job-roles page is an HTML table of links; heuristic scrape of PDF hrefs.
PDF_HREF = re.compile(r'href="(https?://[^"]+\.pdf)"', re.I)
DEVANAGARI_WORD = re.compile(r"[\u0900-\u097F]+(?:[\s\-][\u0900-\u097F]+){0,3}")
# role-code filter to keep it auto-only (ASC = Automotive Skills Council)
AUTO_HINT = re.compile(r"(ASC_Q|automobile|automotive|service technician|mechanic|vehicle)", re.I)


def _http(url: str, timeout: int = 60) -> bytes:
    # URL-encode the path (ASDC hrefs sometimes contain literal spaces)
    from urllib.parse import urlsplit, urlunsplit, quote
    parts = urlsplit(url)
    safe_url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path), parts.query, parts.fragment))
    req = urllib.request.Request(safe_url, headers={
        "User-Agent": "auto-parts-search/0.1 (research)",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_pdf_list() -> list[str]:
    html = _http(INDEX_URL).decode("utf-8", "replace")
    urls = set(PDF_HREF.findall(html))
    # keep only auto-sector-like URLs
    auto = [u for u in urls if AUTO_HINT.search(u) or "qpPdf" in u]
    print(f"discovered {len(urls)} PDFs on index, {len(auto)} look auto-related")
    return sorted(set(auto))


def pdftotext(pdf_path: Path) -> str:
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, timeout=60, text=True,
        )
        return out.stdout
    except FileNotFoundError:
        print("ERROR: pdftotext not installed. `brew install poppler` or `apt install poppler-utils`", file=sys.stderr)
        raise
    except subprocess.TimeoutExpired:
        return ""


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)

    urls = fetch_pdf_list()
    if not urls:
        print("no PDFs found — ASDC page structure may have changed.", file=sys.stderr)
        return

    records = []
    for i, url in enumerate(urls, 1):
        fname = url.rsplit("/", 1)[-1]
        dest = OUT_DIR / fname
        if not dest.exists():
            print(f"[{i}/{len(urls)}] download {fname}")
            try:
                data = _http(url)
                dest.write_bytes(data)
                time.sleep(0.5)  # polite
            except Exception as e:
                print(f"  failed: {e}")
                continue
        text = pdftotext(dest)
        if not text.strip():
            continue
        tokens = sorted(set(m.group(0).strip() for m in DEVANAGARI_WORD.finditer(text)))
        records.append({
            "source_url": url,
            "filename": fname,
            "text_len": len(text),
            "n_devanagari_tokens": len(tokens),
            "devanagari_tokens": tokens[:500],  # cap per-doc
            "text_snippet": text[:1500],
        })
        print(f"  {fname}: {len(text):,} chars, {len(tokens)} Devanagari tokens")

    with PROCESSED.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    all_tokens = set()
    for r in records:
        all_tokens.update(r["devanagari_tokens"])
    print(f"\nwrote {len(records)} QPs -> {PROCESSED}")
    print(f"unique Devanagari tokens across all QPs: {len(all_tokens)}")


if __name__ == "__main__":
    main()
