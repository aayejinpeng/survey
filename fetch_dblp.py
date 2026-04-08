#!/usr/bin/env python3
"""fetch_dblp.py — Step 1: Fetch paper lists from DBLP proceedings.

Extracts paper metadata (title, authors, DOI) from DBLP venue proceedings pages
and writes per-venue-year CSVs to the output directory.

Usage
-----
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --venues MICRO --years 2024
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --force
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DBLP_COLUMNS = [
    "paper_id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "url",
    "dblp_id",
]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config not found: {path}")
    import yaml  # type: ignore[import-untyped]
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


# ---------------------------------------------------------------------------
# HTML fetch with retry
# ---------------------------------------------------------------------------


def _fetch_html(url: str, retries: int = 3) -> str:
    """Fetch HTML with retry for transient errors (429, 5xx, IncompleteRead)."""
    import http.client
    req = urllib.request.Request(url, headers={"User-Agent": "survey-crawler/0.1"})
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 502, 503, 504) and attempt < retries:
                wait = 2 * (attempt + 1)
                print(f"    HTTP {exc.code}, retry {attempt+1}/{retries} in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (http.client.IncompleteRead, urllib.error.URLError, OSError) as exc:
            last_err = exc
            if attempt < retries:
                wait = 2 * (attempt + 1)
                print(f"    {type(exc).__name__}, retry {attempt+1}/{retries} in {wait}s...")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"Fetch failed after {retries} retries: {last_err}")


# ---------------------------------------------------------------------------
# DBLP proceedings parser
# ---------------------------------------------------------------------------


def _parse_papers_from_html(html: str, venue_id: str, year: int, seen_dois: set[str]) -> list[dict[str, Any]]:
    """Parse paper entries from a DBLP HTML page (supports both conference and journal entries)."""
    entry_starts = [
        (m.start(), m.group(1))
        for m in re.finditer(
            r'<li\s[^>]*class="entry (?:inproceedings|article)"[^>]*id="([^"]+)"', html
        )
    ]

    papers: list[dict[str, Any]] = []

    for i, (pos, dblp_id) in enumerate(entry_starts):
        end = entry_starts[i + 1][0] if i + 1 < len(entry_starts) else len(html)
        block = html[pos:end]

        # DOI from nav links
        doi_m = re.findall(r'href="https://doi\.org/([^"]+)"', block)
        doi = doi_m[0] if doi_m else ""

        # COinS: title + authors
        coins = re.findall(r'title="(ctx_ver[^"]*rft\.atitle[^"]*)"', block)
        if not coins:
            continue

        raw = coins[0]
        atitle_m = re.findall(r"rft\.atitle=(.+?)(?:&rft\.)", raw)
        au_m = re.findall(r"rft\.au=(.+?)(?:&rft\.|$)", raw)
        if not atitle_m:
            continue

        title = urllib.parse.unquote_plus(atitle_m[0]).rstrip(".")
        authors = [urllib.parse.unquote_plus(a) for a in au_m]

        # Dedup by DOI
        if doi and doi in seen_dois:
            continue
        if doi:
            seen_dois.add(doi)

        paper_id = f"doi:{doi}" if doi else f"dblp:{dblp_id}"

        papers.append({
            "paper_id": paper_id,
            "title": title,
            "authors": "; ".join(authors),
            "year": str(year),
            "venue": venue_id,
            "doi": doi,
            "url": f"https://doi.org/{doi}" if doi else f"https://dblp.org/rec/{dblp_id}",
            "dblp_id": dblp_id,
        })

    return papers


def fetch_venue_papers(
    venue_id: str, dblp_key: str, year: int, *, dblp_abbr: str | None = None
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch all research papers from a DBLP proceedings page.

    Tries the base URL first. If 404, tries multi-page suffixes (-1, -2, -3, -4).
    Returns (papers, success).
    """
    abbr = dblp_abbr or dblp_key.split("/")[-1]
    base_url = f"https://dblp.org/db/{dblp_key}/{abbr}{year}"

    all_papers: list[dict[str, Any]] = []
    seen_dois: set[str] = set()
    found_any = False

    # Try base URL
    print(f"  Fetching {base_url} ...", end=" ")
    try:
        html = _fetch_html(base_url)
        found_any = True
        papers = _parse_papers_from_html(html, venue_id, year, seen_dois)
        all_papers.extend(papers)
        print(f"{len(papers)} papers")
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            print(f"FAILED (HTTP {exc.code})")
            return [], False
        # 404 — try multi-page suffixes
        print("404, trying multi-page ...", end=" ")
    except Exception as exc:
        print(f"FAILED ({exc})")
        return [], False

    # If base URL 404'd, try -1, -2, -3, -4
    if not found_any:
        page_papers = 0
        for suffix in range(1, 5):
            url = f"{base_url}-{suffix}"
            try:
                html = _fetch_html(url)
                found_any = True
                papers = _parse_papers_from_html(html, venue_id, year, seen_dois)
                all_papers.extend(papers)
                page_papers += len(papers)
            except urllib.error.HTTPError:
                break  # no more pages
            except Exception:
                break

        if found_any:
            print(f"{page_papers} papers (multi-page)")
        else:
            print(f"SKIP (not found, may need manual check)")

    return all_papers, found_any


def _parse_volume_links(html: str, start_year: int, end_year: int) -> list[tuple[int, str]]:
    """Parse volume-year links from a journal index page.
    Returns [(year, url), ...] for volumes within the date range.
    """
    volumes: list[tuple[int, str]] = []
    for m in re.finditer(r'<a[^>]*href="([^"]+)"[^>]*>.*?(?:Volume|Vol\.?)\s*\d+.*?(\d{4})', html, re.IGNORECASE):
        year = int(m.group(2))
        url = m.group(1)
        if start_year <= year <= end_year:
            volumes.append((year, url))
    return volumes


def fetch_journal_papers(
    venue_id: str, dblp_key: str, start_year: int, end_year: int
) -> tuple[dict[int, list[dict[str, Any]]], bool]:
    """Fetch all papers from a DBLP journal within a year range.
    Parses the index page to find volume URLs, then fetches each volume.
    Returns ({year: [papers]}, success).
    """
    index_url = f"https://dblp.org/db/{dblp_key}/index.html"
    print(f"  Index {index_url} ...", end=" ")

    try:
        html = _fetch_html(index_url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"SKIP (404, journal index not found)")
        else:
            print(f"FAILED (HTTP {exc.code})")
        return {}, False
    except Exception as exc:
        print(f"FAILED ({exc})")
        return {}, False

    volumes = _parse_volume_links(html, start_year, end_year)
    if not volumes:
        print(f"SKIP (no volumes found for {start_year}-{end_year})")
        return {}, False

    print(f"{len(volumes)} volumes in range")
    papers_by_year: dict[int, list[dict[str, Any]]] = {}
    seen_dois: set[str] = set()

    for year, vol_url in sorted(volumes, key=lambda x: x[0]):
        print(f"    Volume {year}: {vol_url} ...", end=" ")
        try:
            vol_html = _fetch_html(vol_url)
            papers = _parse_papers_from_html(vol_html, venue_id, year, seen_dois)
            papers_by_year.setdefault(year, []).extend(papers)
            print(f"{len(papers)} papers")
        except Exception as exc:
            print(f"FAILED ({exc})")

    return papers_by_year, bool(papers_by_year)


# ---------------------------------------------------------------------------
# CSV write
# ---------------------------------------------------------------------------


def write_db_csv(papers: list[dict[str, Any]], path: str) -> int:
    """Write papers to CSV. Atomic (.tmp → rename)."""
    import io as _io

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sio = _io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=DBLP_COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for paper in papers:
        row = {col: str(paper.get(col, "")) for col in DBLP_COLUMNS}
        writer.writerow(row)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write(sio.getvalue())
    os.replace(tmp_path, path)
    return len(papers)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="fetch_dblp — Step 1: Fetch paper lists from DBLP proceedings.",
    )
    parser.add_argument("--config", required=True, help="Path to venues.yaml")
    parser.add_argument("--output-dir", required=True, help="Output directory (e.g. data/db/)")
    parser.add_argument("--venues", default=None, help="Only these venues (comma-separated, e.g. ISCA,MICRO)")
    parser.add_argument("--years", default=None, help="Only these years (comma-separated, e.g. 2024)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files (default: skip)")

    args = parser.parse_args(argv)
    config = load_config(args.config)

    venues = config.get("venues", [])
    date_range = config.get("date_range", {})
    start_year = int(date_range.get("start", 2020))
    end_year = int(date_range.get("end", datetime.now().year))

    # Filter venues
    if args.venues:
        allowed = set(v.strip() for v in args.venues.split(","))
        venues = [v for v in venues if v["id"] in allowed]

    # Filter years
    if args.years:
        allowed_years = set(int(y.strip()) for y in args.years.split(","))
    else:
        allowed_years = set(range(start_year, end_year + 1))

    # Header
    venue_ids = [v["id"] for v in venues]
    print(f"\n{'='*60}")
    print(f"  fetch_dblp — DBLP Proceedings Fetch")
    print(f"  Venues: {', '.join(venue_ids)}")
    print(f"  Years:  {sorted(allowed_years)}")
    print(f"{'='*60}\n")

    total_papers = 0
    total_files = 0
    skipped_files = 0

    for venue in venues:
        vid = venue["id"]
        dblp_key = venue["dblp_key"]
        is_journal = dblp_key.startswith("journals/")

        if is_journal:
            # Journal: per-year CSVs (same as conferences)
            papers_by_year, success = fetch_journal_papers(vid, dblp_key, start_year, end_year)
            if success:
                for year in sorted(papers_by_year):
                    if args.years and year not in allowed_years:
                        continue
                    out_name = f"{vid.lower()}-{year}.csv"
                    out_path = os.path.join(args.output_dir, out_name)

                    if os.path.isfile(out_path) and not args.force:
                        print(f"  {out_name}: SKIP (already exists, use --force to overwrite)")
                        skipped_files += 1
                        continue

                    papers = papers_by_year[year]
                    write_db_csv(papers, out_path)
                    total_papers += len(papers)
                    total_files += 1
                    print(f"    → {out_path} ({len(papers)} papers)")
        else:
            # Conference: per-year CSVs
            for year in sorted(allowed_years):
                out_name = f"{vid.lower()}-{year}.csv"
                out_path = os.path.join(args.output_dir, out_name)

                # Skip existing
                if os.path.isfile(out_path) and not args.force:
                    print(f"  {out_name}: SKIP (already exists, use --force to overwrite)")
                    skipped_files += 1
                    continue

                papers, success = fetch_venue_papers(
                    vid, dblp_key, year, dblp_abbr=venue.get("dblp_abbr")
                )
                if success and papers:
                    write_db_csv(papers, out_path)
                    total_papers += len(papers)
                    total_files += 1
                    print(f"    → {out_path} ({len(papers)} papers)")
                elif success and not papers:
                    print(f"    → No papers found for {vid} {year}")

    print(f"\n{'='*60}")
    print(f"  Done: {total_papers} papers from {total_files} venue×year files")
    if skipped_files:
        print(f"  Skipped: {skipped_files} existing files (use --force to overwrite)")
    print(f"  Output dir: {args.output_dir}")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
