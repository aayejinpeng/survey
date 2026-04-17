#!/usr/bin/env python3
"""enrich_papers.py — Step 2: Enrich papers via S2/Crossref/arXiv.

Reads CSVs from data/db/ (or a single file), enriches with abstracts,
citation counts, etc., and writes to data/enriched/.

Usage
-----
# Process all files in data/db/
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# Single file
python3 enrich_papers.py --input data/db/micro-2024.csv --output data/enriched/micro-2024.csv

# Force re-enrich all (including papers that already have abstracts)
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --force

# Only enrich a few papers for testing
python3 enrich_papers.py --input data/db/micro-2024.csv --output data/enriched/micro-2024.csv --limit 5
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: import tools
# ---------------------------------------------------------------------------
_TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")
sys.path.insert(0, _TOOLS_DIR)

import s2_fetch  # our batch-aware S2 client

import arxiv_fetch  # local tools/arxiv_fetch.py (bootstrapped via _TOOLS_DIR above)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Input columns (from fetch_dblp.py)
DBLP_COLUMNS = [
    "paper_id", "title", "authors", "year", "venue", "doi", "url", "dblp_id",
]

# Output columns (enriched)
ENRICHED_COLUMNS = [
    "paper_id",
    "arxiv_id",
    "s2_paper_id",
    "title",
    "authors",
    "year",
    "venue",
    "abstract",
    "source",
    "categories",
    "citation_count",
    "url",
    "doi",
    "published_date",
    "crawled_date",
    "keep",
    "notes",
]

HUMAN_COLUMNS = {"keep", "notes"}

_S2_ENRICH_FIELDS = (
    "paperId,citationCount,abstract,venue,publicationVenue,externalIds,"
    "publicationDate,fieldsOfStudy,openAccessPdf"
)

_MAX_429_WAIT = 30  # seconds


# ---------------------------------------------------------------------------
# Needs-enrichment check
# ---------------------------------------------------------------------------


def needs_enrichment(paper: dict[str, Any]) -> bool:
    """True if paper is missing abstract, has error abstract, or missing citation_count."""
    ab = paper.get("abstract", "")
    if not ab:
        return True
    if ab == "[abstract unavailable]":
        return True
    if ab.startswith("[error:"):
        return True
    cc = str(paper.get("citation_count", ""))
    if not cc or cc in ("0", ""):
        return True
    return False


# ---------------------------------------------------------------------------
# API helpers with 429 retry
# ---------------------------------------------------------------------------


def _call_with_429_retry(
    fn,
    *args,
    max_retries: int = 3,
    base_wait: float = 2.0,
    label: str = "",
) -> tuple[Any | None, str | None]:
    """Call fn with exponential backoff on 429 errors."""
    for attempt in range(max_retries):
        try:
            result = fn(*args)
            return result, None
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = base_wait * (2 ** attempt)
                if wait > _MAX_429_WAIT:
                    tag = f"[error: 429 rate-limited after {attempt+1} retries]"
                    print(f"      [{label}] 429 gave up after {attempt+1} retries", file=sys.stderr)
                    return None, tag
                print(f"      [{label}] 429, retry {attempt+1}/{max_retries} in {wait:.0f}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            tag = f"[error: HTTP {exc.code}]"
            return None, tag
        except Exception as exc:
            tag = f"[error: {exc}]"
            return None, tag
    tag = f"[error: 429 rate-limited after {max_retries} retries]"
    return None, tag


def _request_json(url: str, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "survey-crawler/0.1 (mailto:research@example.com)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean_crossref_abstract(raw: str) -> str:
    """Clean Crossref abstract: strip all <jats:...> tags."""
    text = re.sub(r"</?jats:[^>]*>", "", raw)
    return text.strip()


def _normalize_title(title: str) -> str:
    """Normalize titles for lightweight exact matching."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


# ---------------------------------------------------------------------------
# Enrichment: S2
# ---------------------------------------------------------------------------


def _apply_s2_data(paper: dict[str, Any], s2_data: dict[str, Any]) -> None:
    """Write S2 fields into a paper dict."""
    paper["citation_count"] = s2_data.get("citationCount", 0) or 0
    paper["s2_paper_id"] = s2_data.get("paperId", "")

    if s2_data.get("abstract"):
        ab = paper.get("abstract", "")
        if not ab or ab == "[abstract unavailable]" or ab.startswith("[error:"):
            paper["abstract"] = s2_data["abstract"]

    ext = s2_data.get("externalIds") or {}
    if ext.get("ArXiv"):
        paper["arxiv_id"] = ext["ArXiv"]
    if s2_data.get("publicationDate"):
        paper["published_date"] = s2_data["publicationDate"][:10]
    fos = s2_data.get("fieldsOfStudy") or []
    if fos and not paper.get("categories"):
        paper["categories"] = "; ".join(fos)


def enrich_from_s2(
    papers: list[dict[str, Any]],
) -> tuple[int, int]:
    """Enrich papers via S2 batch API. Returns (enriched_count, abstract_filled).

    Uses POST /paper/batch — one request per 500 papers instead of one per paper.
    """
    eligible = [(i, p) for i, p in enumerate(papers) if p.get("doi")]
    if not eligible:
        return 0, 0

    # Build ID list for batch request
    s2_ids = [f"DOI:{p['doi']}" for _, p in eligible]

    print(f"  Batch fetching {len(s2_ids)} papers from S2...", file=sys.stderr)
    try:
        results = s2_fetch.get_papers_batch(s2_ids, fields=_S2_ENRICH_FIELDS)
    except RuntimeError as exc:
        # Batch failed entirely — mark all as errors
        err_tag = f"[error: S2 batch failed: {exc}]"
        for _, paper in eligible:
            paper["abstract"] = err_tag
        print(f"  S2 batch FAILED: {exc}", file=sys.stderr)
        return 0, 0

    enriched = 0
    abstracts = 0

    for (orig_idx, paper), s2_data in zip(eligible, results):
        if s2_data is None:
            # Paper not found in S2 — not an error, just no data
            continue
        _apply_s2_data(paper, s2_data)
        enriched += 1
        if paper.get("abstract") and not paper["abstract"].startswith("["):
            abstracts += 1

    print(f"  S2 result: {enriched}/{len(eligible)} enriched, {abstracts} abstracts")
    return enriched, abstracts


def enrich_from_s2_title_search(
    papers: list[dict[str, Any]],
) -> tuple[int, int]:
    """Enrich papers without DOI via S2 title search API (one-by-one).
    Only processes papers that still have no abstract and no DOI.
    Returns (enriched_count, abstract_filled).
    """
    missing = [
        (i, p) for i, p in enumerate(papers)
        if not p.get("doi")
        and (not p.get("abstract") or p["abstract"] in ("", "[abstract unavailable]")
             or p["abstract"].startswith("[error:"))
    ]
    if not missing:
        return 0, 0

    print(f"  Title-searching {len(missing)} papers without DOI from S2...", file=sys.stderr)
    enriched = 0
    abstracts = 0

    for idx, (orig_idx, paper) in enumerate(missing):
        title = paper.get("title", "").strip()
        if not title:
            continue

        result, err = _call_with_429_retry(
            lambda t=title: s2_fetch.search(t, max_results=5, fields=_S2_ENRICH_FIELDS),
            max_retries=3,
            base_wait=3.0,
            label=f"#{idx+1}",
        )
        if err or not result:
            paper["abstract"] = err or "[abstract unavailable]"
            continue

        data = result.get("data") or []
        if not data:
            paper["abstract"] = "[abstract unavailable]"
            continue

        paper_year = str(paper.get("year", "")).strip()
        paper_title_norm = _normalize_title(title)
        s2_paper = None
        for candidate in data:
            candidate_title = candidate.get("title") or ""
            candidate_title_norm = _normalize_title(candidate_title)
            candidate_year = str(candidate.get("year", "")).strip()
            same_title = candidate_title_norm == paper_title_norm
            same_year = not paper_year or not candidate_year or candidate_year == paper_year
            if same_title and same_year:
                s2_paper = candidate
                break
        if s2_paper is None:
            paper["abstract"] = "[abstract unavailable]"
            continue

        _apply_s2_data(paper, s2_paper)
        enriched += 1
        if paper.get("abstract") and not paper["abstract"].startswith("["):
            abstracts += 1
            print(f"    [{idx+1}/{len(missing)}] Found: {title[:60]}...")
        else:
            print(f"    [{idx+1}/{len(missing)}] No abstract: {title[:60]}...")

        # Rate limit: S2 free tier ~1 req/s without key
        time.sleep(1.0)

    return enriched, abstracts


def enrich_from_s2_venue_bulk(
    papers: list[dict[str, Any]],
) -> tuple[int, int]:
    """Bulk-fetch venue/year candidate pools, then exact-match titles locally.

    This reduces request count for conference-program CSVs where many papers
    share the same venue and year.
    """
    missing = [
        p for p in papers
        if not p.get("doi")
        and (not p.get("abstract") or p["abstract"] in ("", "[abstract unavailable]")
             or p["abstract"].startswith("[error:"))
    ]
    if not missing:
        return 0, 0

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for paper in missing:
        venue = str(paper.get("venue", "")).strip()
        year = str(paper.get("year", "")).strip()
        if not venue or not year:
            continue
        groups.setdefault((venue, year), []).append(paper)

    if not groups:
        return 0, 0

    enriched = 0
    abstracts = 0
    for (venue, year), group in groups.items():
        query = venue
        limit = min(max(len(group) * 4, 25), 200)
        result, err = _call_with_429_retry(
            lambda q=query, y=year, v=venue, m=limit: s2_fetch.search_bulk(
                q,
                max_results=m,
                fields=_S2_ENRICH_FIELDS,
                year=y,
                venue=v,
            ),
            max_retries=3,
            base_wait=3.0,
            label=f"bulk {venue} {year}",
        )
        if err or not result:
            continue

        candidates = result.get("data") or []
        if not candidates:
            continue

        by_title: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            candidate_title = candidate.get("title") or ""
            candidate_year = str(candidate.get("year", "")).strip()
            norm_title = _normalize_title(candidate_title)
            if not norm_title:
                continue
            if candidate_year and candidate_year != year:
                continue
            by_title.setdefault(norm_title, candidate)

        matched_here = 0
        for paper in group:
            norm_title = _normalize_title(str(paper.get("title", "")))
            if not norm_title:
                continue
            candidate = by_title.get(norm_title)
            if not candidate:
                continue
            _apply_s2_data(paper, candidate)
            enriched += 1
            matched_here += 1
            if paper.get("abstract") and not str(paper["abstract"]).startswith("["):
                abstracts += 1

        if matched_here:
            print(
                f"  Bulk-matched {matched_here}/{len(group)} papers for venue={venue!r}, year={year}"
            )

    return enriched, abstracts


# ---------------------------------------------------------------------------
# Enrichment: Crossref fallback
# ---------------------------------------------------------------------------


def _fill_from_crossref(paper: dict[str, Any]) -> tuple[bool, str | None]:
    """Try to fill abstract from Crossref API via DOI."""
    doi = paper.get("doi", "")
    if not doi:
        return False, None

    url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
    result, err = _call_with_429_retry(
        lambda u=url: _request_json(u),
        max_retries=3,
        base_wait=2.0,
        label=f"Crossref {doi}",
    )
    if err:
        return False, err
    if result:
        abstract = result.get("message", {}).get("abstract", "")
        if abstract:
            paper["abstract"] = _clean_crossref_abstract(abstract)
            return True, None
    return False, None


# ---------------------------------------------------------------------------
# Enrichment: arXiv fallback
# ---------------------------------------------------------------------------


def _fill_from_arxiv(paper: dict[str, Any]) -> tuple[bool, str | None]:
    """Try to fill abstract from arXiv API via arxiv_id."""
    aid = paper.get("arxiv_id", "")
    if not aid:
        return False, None

    result, err = _call_with_429_retry(
        lambda a=aid: arxiv_fetch.search(f"id:{a}", max_results=1),
        max_retries=3,
        base_wait=2.0,
        label=f"arXiv {aid}",
    )
    if err:
        return False, err
    if result and result[0].get("abstract"):
        paper["abstract"] = result[0]["abstract"]
        return True, None
    return False, None


# ---------------------------------------------------------------------------
# Enrichment: fallback chain
# ---------------------------------------------------------------------------


def enrich_abstracts(
    papers: list[dict[str, Any]],
    crossref_enabled: bool = True,
    arxiv_enabled: bool = True,
) -> tuple[int, int, int]:
    """Fill missing abstracts via fallback chain. Returns (crossref, arxiv, unavailable)."""
    cr_count = 0
    arxiv_count = 0
    unavailable = 0

    missing = [p for p in papers if not p.get("abstract")
               or p.get("abstract") == ""
               or p.get("abstract") == "[abstract unavailable]"
               or (p.get("abstract") or "").startswith("[error:")]
    total_missing = len(missing)

    for i, paper in enumerate(missing):
        progress = f"    [{i+1}/{total_missing}]"

        # Layer 1: Crossref
        if crossref_enabled:
            ok, err = _fill_from_crossref(paper)
            if ok:
                cr_count += 1
                if (i + 1) % 10 == 0 or i == total_missing - 1:
                    print(f"{progress} Crossref OK  (cr: {cr_count}, arxiv: {arxiv_count}, unavail: {unavailable})")
                continue
            if err:
                paper["abstract"] = err
                unavailable += 1
                continue

        # Layer 2: arXiv
        if arxiv_enabled:
            ok, err = _fill_from_arxiv(paper)
            if ok:
                arxiv_count += 1
                time.sleep(1.0)
                if (i + 1) % 10 == 0 or i == total_missing - 1:
                    print(f"{progress} arXiv OK  (cr: {cr_count}, arxiv: {arxiv_count}, unavail: {unavailable})")
                continue
            if err:
                paper["abstract"] = err
                unavailable += 1
                continue

        # Layer 3: Mark unavailable
        if (
            not paper.get("abstract")
            or paper.get("abstract") == "[abstract unavailable]"
            or (paper.get("abstract") or "").startswith("[error:")
        ):
            if not paper.get("abstract"):
                paper["abstract"] = "[abstract unavailable]"
            unavailable += 1

    return cr_count, arxiv_count, unavailable


# ---------------------------------------------------------------------------
# CSV read/write
# ---------------------------------------------------------------------------


def read_csv(path: str) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Read CSV, return (rows, human_annotations_by_paper_id)."""
    if not os.path.isfile(path):
        return [], {}
    rows: list[dict[str, str]] = []
    human: dict[str, dict[str, str]] = {}
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row.get("paper_id", "")
            rows.append(row)
            if pid:
                human[pid] = {
                    "keep": row.get("keep", ""),
                    "notes": row.get("notes", ""),
                }
    return rows, human


def write_csv(
    papers: list[dict[str, Any]],
    path: str,
    existing_human: dict[str, dict[str, str]] | None = None,
) -> int:
    """Write papers to CSV. Atomic (.tmp → rename). Preserves human columns."""
    if existing_human is None:
        existing_human = {}

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    sio = io.StringIO()
    writer = csv.DictWriter(sio, fieldnames=ENRICHED_COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for paper in papers:
        row = {col: str(paper.get(col, "")) for col in ENRICHED_COLUMNS}
        pid = row["paper_id"]
        if pid in existing_human:
            row["keep"] = existing_human[pid].get("keep", "")
            row["notes"] = existing_human[pid].get("notes", "")
        writer.writerow(row)

    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write(sio.getvalue())
    os.replace(tmp_path, path)
    return len(papers)


# ---------------------------------------------------------------------------
# Core enrichment pipeline for a single file
# ---------------------------------------------------------------------------


def enrich_file(
    input_path: str,
    output_path: str,
    force: bool = False,
    no_s2: bool = False,
    no_crossref: bool = False,
    no_arxiv: bool = False,
    limit: int = 0,
) -> int:
    """Enrich a single CSV file. Returns 0 on success."""
    rows, existing_human = read_csv(input_path)
    if not rows:
        print(f"No papers found in {input_path}")
        return 1

    # Normalize rows: add missing enrichment columns with defaults
    all_papers: list[dict[str, Any]] = []
    for row in rows:
        paper = dict(row)
        # Ensure enrichment columns exist with defaults
        for col in ENRICHED_COLUMNS:
            if col not in paper or paper[col] is None:
                if col == "abstract":
                    paper[col] = ""
                elif col == "citation_count":
                    paper[col] = 0
                elif col == "source":
                    paper[col] = "dblp"
                elif col == "crawled_date":
                    from datetime import datetime, timezone
                    paper[col] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                else:
                    paper[col] = ""
        all_papers.append(paper)

    # Select papers to enrich
    if force:
        to_enrich = all_papers
        skipped = 0
    else:
        to_enrich = [p for p in all_papers if needs_enrichment(p)]
        skipped = len(all_papers) - len(to_enrich)

    # Apply limit
    if limit > 0 and to_enrich:
        to_enrich = to_enrich[:limit]
        print(f"  Limit: processing first {limit} papers")

    fname = os.path.basename(input_path)
    print(f"\nProcessing {fname} ({len(all_papers)} papers)")
    print(f"  Need enrichment: {len(to_enrich)} (skipped: {skipped} already complete)")

    if not to_enrich:
        print("  Nothing to enrich. Use --force to re-enrich everything.")
        return 0

    # ── Phase B: S2 enrichment ──
    print("  ── S2 enrichment ──")
    if not no_s2:
        eligible = sum(1 for p in to_enrich if p.get("doi"))
        print(f"  Papers with DOI: {eligible}/{len(to_enrich)}")
        enriched, s2_abstracts = enrich_from_s2(to_enrich)
        print(f"  S2 result: {enriched} enriched, {s2_abstracts} abstracts")

        # Phase B2: Title search for papers without DOI
        no_doi_missing = sum(
            1 for p in to_enrich
            if not p.get("doi")
            and (not p.get("abstract") or p["abstract"] in ("", "[abstract unavailable]")
                 or p["abstract"].startswith("[error:"))
        )
        if no_doi_missing > 0:
            print(f"  ── S2 venue/year bulk candidate match ({no_doi_missing} papers without DOI) ──")
            bulk_enriched, bulk_abstracts = enrich_from_s2_venue_bulk(to_enrich)
            print(f"  Venue/year bulk result: {bulk_enriched} enriched, {bulk_abstracts} abstracts")

            no_doi_missing = sum(
                1 for p in to_enrich
                if not p.get("doi")
                and (not p.get("abstract") or p["abstract"] in ("", "[abstract unavailable]")
                     or p["abstract"].startswith("[error:"))
            )
        if no_doi_missing > 0:
            print(f"  ── S2 title search fallback ({no_doi_missing} papers without DOI) ──")
            ts_enriched, ts_abstracts = enrich_from_s2_title_search(to_enrich)
            print(f"  Title search result: {ts_enriched} enriched, {ts_abstracts} abstracts")
    else:
        print("  SKIPPED (--no-s2)")

    # ── Phase C: Abstract fallback ──
    def _is_missing_abstract(p):
        ab = p.get("abstract", "")
        return not ab or ab == "[abstract unavailable]" or ab.startswith("[error:")

    missing = sum(1 for p in to_enrich if _is_missing_abstract(p))
    have_abstract = len(to_enrich) - missing

    print("  ── Abstract fallback ──")
    print(f"  Status: {have_abstract} have, {missing} missing")
    if missing > 0 and (not no_crossref or not no_arxiv):
        cr_count, arxiv_count, unavail = enrich_abstracts(
            to_enrich,
            crossref_enabled=not no_crossref,
            arxiv_enabled=not no_arxiv,
        )
        print(f"  Fallback result: Crossref={cr_count}, arXiv={arxiv_count}, unavailable={unavail}")
    elif missing > 0:
        print("  SKIPPED (all enrichment disabled)")
    else:
        print("  All abstracts filled, nothing to do")

    # ── Merge back ──
    enriched_by_id = {p["paper_id"]: p for p in to_enrich}
    for row in all_papers:
        pid = row.get("paper_id", "")
        if pid in enriched_by_id:
            ep = enriched_by_id[pid]
            for col in ENRICHED_COLUMNS:
                if col in HUMAN_COLUMNS:
                    continue
                new_val = str(ep.get(col, ""))
                old_val = str(row.get(col, ""))
                if new_val and (not old_val or new_val != old_val):
                    row[col] = new_val

    write_csv(all_papers, output_path, existing_human)
    print(f"  Written: {len(all_papers)} papers to {output_path}")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="enrich_papers — Step 2: Enrich papers via S2/Crossref/arXiv.",
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-dir", help="Input directory (data/db/)")
    input_group.add_argument("--input", help="Single input file")

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument("--output-dir", help="Output directory (data/enriched/)")
    output_group.add_argument("--output", help="Single output file")

    parser.add_argument("--force", action="store_true", help="Re-enrich all (default: only missing)")
    parser.add_argument("--no-s2", action="store_true", help="Skip S2 enrichment")
    parser.add_argument("--no-crossref", action="store_true", help="Skip Crossref fallback")
    parser.add_argument("--no-arxiv", action="store_true", help="Skip arXiv fallback")
    parser.add_argument("--limit", type=int, default=0, help="Only enrich N papers (for testing)")

    args = parser.parse_args(argv)

    # Header
    print(f"\n{'='*60}")
    print(f"  enrich_papers — S2/Crossref/arXiv Enrichment")
    if args.input_dir:
        print(f"  Input dir:  {args.input_dir}")
    else:
        print(f"  Input:      {args.input}")
    print(f"{'='*60}")

    if args.input_dir and args.output_dir:
        # Directory mode: process all CSVs in input dir
        csv_files = sorted(Path(args.input_dir).glob("*.csv"))
        if not csv_files:
            print(f"\nNo CSV files found in {args.input_dir}")
            return 1

        for csv_path in csv_files:
            out_path = os.path.join(args.output_dir, csv_path.name)
            enrich_file(
                str(csv_path), out_path,
                force=args.force,
                no_s2=args.no_s2,
                no_crossref=args.no_crossref,
                no_arxiv=args.no_arxiv,
                limit=args.limit,
            )
    else:
        # Single file mode
        if not args.input or not args.output:
            print("Must specify --input and --output (or --input-dir and --output-dir)")
            return 1
        enrich_file(
            args.input, args.output,
            force=args.force,
            no_s2=args.no_s2,
            no_crossref=args.no_crossref,
            no_arxiv=args.no_arxiv,
            limit=args.limit,
        )

    print(f"\n{'='*60}")
    print(f"  Enrichment complete")
    print(f"{'='*60}\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
