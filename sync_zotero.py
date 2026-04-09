#!/usr/bin/env python3
"""sync_zotero.py — Download PDFs from Zotero local API by DOI.

Prerequisites:
  - Zotero desktop running with local API enabled (default: localhost:23119)
  - Papers already imported into Zotero (via DOI or RIS import)
  - Zotero has synced/attached PDFs

Usage
-----
# Download all keep papers from scored CSV
python3 sync_zotero.py --input data/topics/cpu-ai/scored-score-gte11.csv --output-dir pdfs/cpu-ai/

# Dry run (just check what's in Zotero)
python3 sync_zotero.py --input data/topics/cpu-ai/scored-score-gte11.csv --output-dir pdfs/cpu-ai/ --dry-run

# Custom Zotero port
python3 sync_zotero.py --input data/topics/cpu-ai/scored-score-gte11.csv --output-dir pdfs/cpu-ai/ --port 23119
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import shutil
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ZOTERO_API_BASE = "http://{host}:{port}/api/users/0"
_CHUNK = 64 * 1024


def _request(url: str, timeout: int = 15) -> dict[str, Any] | None:
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "sync-zotero/1.0",
            "Zotero-API-Version": "3",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError:
        return None
    except Exception:
        return None


def check_zotero(host: str, port: int) -> bool:
    """Check if Zotero local API is running."""
    url = f"http://{host}:{port}/connector/ping"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def find_item_by_doi(doi: str, host: str, port: int) -> dict[str, Any] | None:
    """Search Zotero library for an item by DOI."""
    base = ZOTERO_API_BASE.format(host=host, port=port)
    doi_clean = doi.strip().lower()

    # Method 1: Search by DOI field directly
    url = f"{base}/items?q={urllib.parse.quote(doi_clean, safe='')}&limit=25"
    data = _request(url)
    if data:
        for item in data:
            d = item.get("data", {})
            if d.get("DOI", "").strip().lower() == doi_clean:
                return item

    # Method 2: Iterate recent items and match DOI (covers items not found via search)
    url2 = f"{base}/items?limit=100&sort=dateAdded&direction=desc&start=0"
    data2 = _request(url2)
    if data2:
        for item in data2:
            d = item.get("data", {})
            if d.get("DOI", "").strip().lower() == doi_clean:
                return item
            if doi_clean in d.get("url", "").lower():
                return item

    # Method 3: Try wider search with partial DOI prefix
    doi_prefix = doi_clean.split("/")[0] if "/" in doi_clean else doi_clean[:8]
    url3 = f"{base}/items?q={urllib.parse.quote(doi_prefix, safe='')}&limit=50"
    data3 = _request(url3)
    if data3:
        for item in data3:
            d = item.get("data", {})
            if d.get("DOI", "").strip().lower() == doi_clean:
                return item

    return None


def get_pdf_attachment(item_key: str, host: str, port: int) -> dict[str, Any] | None:
    """Find PDF attachment for a Zotero item."""
    url = f"{ZOTERO_API_BASE.format(host=host, port=port)}/items/{item_key}/children"
    children = _request(url)
    if not children:
        return None

    for child in children:
        d = child.get("data", {})
        ct = d.get("contentType", "")
        if "pdf" in ct.lower():
            return child
        link_mode = d.get("linkMode", "")
        title = d.get("title", "").lower()
        if "pdf" in title or link_mode in ("imported_file", "imported_url"):
            return child

    return None


def download_pdf(attachment_key: str, dest: str, host: str, port: int) -> bool:
    """Download a PDF attachment from Zotero.

    Handles linked files that return a 302 redirect to file:// URLs
    by copying directly from the local filesystem.
    """
    url = f"{ZOTERO_API_BASE.format(host=host, port=port)}/items/{attachment_key}/file"
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "sync-zotero/1.0",
            "Zotero-API-Version": "3",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                with open(dest, "wb") as f:
                    while True:
                        chunk = resp.read(_CHUNK)
                        if not chunk:
                            break
                        f.write(chunk)
            return True
        except urllib.error.HTTPError as exc:
            # Handle 302 redirect to file:// — copy from local path
            if exc.code == 302 and exc.headers.get("Location", "").startswith("file://"):
                local_path = urllib.parse.unquote(
                    exc.headers["Location"][7:]  # strip "file://"
                )
                if os.path.isfile(local_path):
                    shutil.copy2(local_path, dest)
                    return True
                print(f"    Local file not found: {local_path}", file=sys.stderr)
                return False
            raise
    except Exception as exc:
        print(f"    Download error: {exc}", file=sys.stderr)
        return False


def _sanitize_filename(title: str, max_len: int = 80) -> str:
    name = re.sub(r"[^\w\s\-]", "", title).strip()
    name = re.sub(r"[\s]+", "-", name)
    return name[:max_len]


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync PDFs from Zotero by DOI.")
    parser.add_argument("--input", required=True, help="Scored CSV file")
    parser.add_argument("--output-dir", required=True, help="Directory to save PDFs")
    parser.add_argument("--host", default="localhost", help="Zotero host (use host.docker.internal from Docker)")
    parser.add_argument("--port", type=int, default=23119, help="Zotero local API port")
    parser.add_argument("--marks", default="keep,core,related", help="Which marks to sync")
    parser.add_argument("--dry-run", action="store_true", help="Only check, don't download")
    args = parser.parse_args()

    if not check_zotero(args.host, args.port):
        print(f"Error: Zotero not running on {args.host}:{args.port}", file=sys.stderr)
        print("  Make sure Zotero desktop is open and local API is enabled.", file=sys.stderr)
        return 1

    print(f"Zotero connected on {args.host}:{args.port}")

    with open(args.input, encoding="utf-8") as f:
        papers = list(csv.DictReader(f))

    allowed_marks = set(m.strip().lower() for m in args.marks.split(","))
    kept = [p for p in papers if (p.get("keep", "") or "").strip().lower() in allowed_marks]

    if not kept:
        print(f"No papers matched marks={args.marks}")
        return 0

    Path(args.output_dir).mkdir(parents=True, exist_ok=True)
    print(f"Syncing {len(kept)} papers from Zotero...\n")

    downloaded = 0
    not_found = 0
    no_pdf = 0

    for i, p in enumerate(kept):
        title = p.get("title", "unknown")
        doi = p.get("doi", "").strip()
        fname = f"{_sanitize_filename(title)}.pdf"
        fpath = os.path.join(args.output_dir, fname)

        print(f"  [{i+1}/{len(kept)}] {title[:60]}")

        if os.path.isfile(fpath):
            print(f"    SKIP (already exists)")
            downloaded += 1
            continue

        if not doi:
            print(f"    SKIP (no DOI)")
            not_found += 1
            continue

        # Find item in Zotero
        item = find_item_by_doi(doi, args.host, args.port)
        if not item:
            print(f"    NOT FOUND in Zotero (DOI: {doi})")
            not_found += 1
            continue

        item_key = item["key"]

        # Find PDF attachment
        attachment = get_pdf_attachment(item_key, args.host, args.port)
        if not attachment:
            print(f"    NO PDF attachment in Zotero")
            no_pdf += 1
            continue

        if args.dry_run:
            print(f"    FOUND PDF: {attachment.get('data', {}).get('filename', '?')}")
            downloaded += 1
            continue

        # Download
        att_key = attachment["key"]
        print(f"    Downloading...", end=" ", flush=True)
        if download_pdf(att_key, fpath, args.host, args.port):
            print(f"OK -> {fname}")
            downloaded += 1
        else:
            print("FAILED")

    print(f"\n{'='*50}")
    print(f"  Downloaded: {downloaded}/{len(kept)}")
    print(f"  Not in Zotero: {not_found}")
    print(f"  No PDF: {no_pdf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
