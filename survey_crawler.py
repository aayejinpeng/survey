#!/usr/bin/env python3
"""Survey Crawler v2: DBLP venue-based discovery + S2/Crossref/arXiv enrichment.

Pipeline: DBLP proceedings → S2 enrichment (DOI) → Crossref/arXiv abstract fallback → CSV

Usage
-----
python3 survey_crawler.py crawl \\
    --config .claude/survey-data/{topic}/config.yaml \\
    --output .claude/survey-data/{topic}/abstracts.csv \\
    --state  .claude/survey-data/{topic}/crawl-state.json \\
    --mode   full|update
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Bootstrap: import existing tools
# ---------------------------------------------------------------------------
_TOOLS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "sleep-work-agent",
    "Auto-claude-code-research-in-sleep",
    "tools",
)
sys.path.insert(0, _TOOLS_DIR)

import arxiv_fetch  # type: ignore[import-untyped]
import semantic_scholar_fetch as s2_fetch  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CSV_COLUMNS = [
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

# ---------------------------------------------------------------------------
# Config / State helpers
# ---------------------------------------------------------------------------


def _slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def load_config(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config not found: {path}")
    import yaml  # type: ignore[import-untyped]
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_state(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {
            "topic_slug": "",
            "last_full_crawl": None,
            "last_incremental_crawl": None,
            "seen_paper_ids": [],
            "crawled_venues": [],
            "crawl_history": [],
        }
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Phase A: DBLP Proceedings Fetch (HTML)
# ---------------------------------------------------------------------------


def _fetch_html(url: str, retries: int = 2) -> str:
    """Fetch HTML with retry for transient errors (429, 5xx)."""
    req = urllib.request.Request(url, headers={"User-Agent": "survey-crawler/0.1"})
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (429, 502, 503, 504) and attempt < retries:
                wait = 2 * (attempt + 1)
                print(f"    HTTP {exc.code}, retry {attempt+1}/{retries} in {wait}s...")
                time.sleep(wait)
                continue
            raise
        except (urllib.error.URLError, OSError) as exc:
            last_err = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    raise RuntimeError(f"Fetch failed after {retries} retries: {last_err}")


def fetch_venue_papers(venue_id: str, dblp_key: str, year: int) -> tuple[list[dict[str, Any]], bool]:
    """Fetch all research papers from a DBLP proceedings page.
    Returns (papers, success).
    """
    abbr = dblp_key.split("/")[-1]
    url = f"https://dblp.org/db/{dblp_key}/{abbr}{year}"
    print(f"  Fetching {url} ...", end=" ")

    try:
        html = _fetch_html(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            print(f"SKIP (404, proceedings not found)")
        else:
            print(f"FAILED (HTTP {exc.code})")
        return [], False
    except Exception as exc:
        print(f"FAILED ({exc})")
        return [], False

    # Find entry boundaries
    entry_starts = [
        (m.start(), m.group(1))
        for m in re.finditer(
            r'<li\s[^>]*class="entry inproceedings"[^>]*id="([^"]+)"', html
        )
    ]

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    papers: list[dict[str, Any]] = []
    seen_dois: set[str] = set()

    for i, (pos, dblp_id) in enumerate(entry_starts):
        end = entry_starts[i + 1][0] if i + 1 < len(entry_starts) else len(html)
        block = html[pos:end]

        # DOI from nav links
        doi_m = re.findall(r'href="https://doi\.org/([^"]+)"', block)
        doi = doi_m[0] if doi_m else ""

        # COinS: title + authors (appears after the </li>, within the block)
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
            "arxiv_id": "",
            "s2_paper_id": "",
            "title": title,
            "authors": "; ".join(authors),
            "year": str(year),
            "venue": venue_id,
            "abstract": "",
            "source": "dblp",
            "categories": "",
            "citation_count": 0,
            "url": f"https://doi.org/{doi}" if doi else f"https://dblp.org/rec/{dblp_id}",
            "doi": doi,
            "published_date": f"{year}-01-01",
            "crawled_date": today,
            "keep": "",
            "notes": "",
        })

    print(f"{len(papers)} papers")
    return papers, True


def fetch_all_venues(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Fetch papers from all configured venues × years.
    Returns (papers, failures) where failures = [{venue, year, error}].
    """
    venues = config.get("venues", [])
    date_range = config.get("date_range", {})
    start_year = int(date_range.get("start", 2020))
    end_year = int(date_range.get("end", datetime.now().year))

    all_papers: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    seen_ids: set[str] = set()

    for venue in venues:
        vid = venue["id"]
        dblp_key = venue["dblp_key"]
        for year in range(start_year, end_year + 1):
            papers, success = fetch_venue_papers(vid, dblp_key, year)
            if not success:
                failures.append({"venue": vid, "year": str(year), "error": "fetch failed"})
            for p in papers:
                if p["paper_id"] not in seen_ids:
                    seen_ids.add(p["paper_id"])
                    all_papers.append(p)

    return all_papers, failures


# ---------------------------------------------------------------------------
# Phase B: S2 Enrichment (via DOI)
# ---------------------------------------------------------------------------


_MAX_429_WAIT = 30  # seconds — give up if we'd need to wait longer


def _call_with_429_retry(
    fn,
    *args,
    max_retries: int = 3,
    base_wait: float = 2.0,
    label: str = "",
) -> tuple[Any | None, str | None]:
    """Call fn with exponential backoff on 429 errors.

    Returns (result, error_tag).
    - result: fn's return value on success, None on failure
    - error_tag: None on success, or a human-readable error string for the abstract column
    """
    for attempt in range(max_retries):
        try:
            result = fn(*args)
            return result, None
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                wait = base_wait * (2 ** attempt)  # 2, 4, 8, ...
                if wait > _MAX_429_WAIT:
                    tag = f"[error: 429 rate-limited after {attempt+1} retries, please fetch manually]"
                    print(f"      [{label}] 429 gave up after {attempt+1} retries (would wait {wait:.0f}s)", file=sys.stderr)
                    return None, tag
                print(f"      [{label}] 429, retry {attempt+1}/{max_retries} in {wait:.0f}s...", file=sys.stderr)
                time.sleep(wait)
                continue
            tag = f"[error: HTTP {exc.code}, please fetch manually]"
            return None, tag
        except Exception as exc:
            tag = f"[error: {exc}, please fetch manually]"
            return None, tag
    tag = f"[error: 429 rate-limited after {max_retries} retries, please fetch manually]"
    return None, tag


def enrich_from_s2(
    papers: list[dict[str, Any]],
    delay: float = 1.1,
    enabled: bool = True,
) -> tuple[int, int]:
    """Enrich papers via S2 DOI lookup. Returns (enriched_count, abstract_filled)."""
    if not enabled:
        return 0, 0

    enriched = 0
    abstracts = 0
    failed = 0

    eligible = [p for p in papers if p.get("doi")]
    total = len(eligible)

    for i, paper in enumerate(eligible):
        doi = paper["doi"]
        progress = f"    [{i+1}/{total}]"
        label = f"S2 {doi}"

        result, err = _call_with_429_retry(
            lambda d=doi: s2_fetch.get_paper(f"DOI:{d}", fields=_S2_ENRICH_FIELDS),
            max_retries=3,
            base_wait=2.0,
            label=label,
        )

        if err:
            failed += 1
            # Write error into abstract column if current value is a placeholder
            ab = paper.get("abstract", "")
            if not ab or ab in ("[abstract unavailable]",) or ab.startswith("[error:"):
                paper["abstract"] = err
            print(f"{progress} S2 FAIL: {err}")
        elif result:
            s2_data = result
            paper["citation_count"] = s2_data.get("citationCount", 0) or 0
            paper["s2_paper_id"] = s2_data.get("paperId", "")

            # Write S2 abstract if current value is empty or a placeholder
            if s2_data.get("abstract"):
                ab = paper.get("abstract", "")
                if not ab or ab == "[abstract unavailable]" or ab.startswith("[error:"):
                    paper["abstract"] = s2_data["abstract"]
                    abstracts += 1

            ext = s2_data.get("externalIds") or {}
            if ext.get("ArXiv"):
                paper["arxiv_id"] = ext["ArXiv"]
            if s2_data.get("publicationDate") and paper["published_date"] == f"{paper['year']}-01-01":
                paper["published_date"] = s2_data["publicationDate"][:10]
            fos = s2_data.get("fieldsOfStudy") or []
            if fos and not paper["categories"]:
                paper["categories"] = "; ".join(fos)

            enriched += 1
            if i == 0 or (i + 1) % 10 == 0 or i == total - 1:
                print(f"{progress} S2 OK  (enriched: {enriched}, abstracts: {abstracts}, failed: {failed})")

        time.sleep(delay)

    return enriched, abstracts


# ---------------------------------------------------------------------------
# Phase C: Abstract Fallback Chain
# ---------------------------------------------------------------------------


def _request_json(url: str, timeout: int = 15) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "User-Agent": "survey-crawler/0.1 (mailto:research@example.com)",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _clean_crossref_abstract(raw: str) -> str:
    """Clean Crossref abstract: strip all <jats:...> tags."""
    text = re.sub(r"</?jats:[>]*>", "", raw)
    return text.strip()


def _fill_from_crossref(paper: dict[str, Any]) -> tuple[bool, str | None]:
    """Try to fill abstract from Crossref API via DOI.
    Returns (success, error_tag).
    """
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


def _fill_from_arxiv(paper: dict[str, Any]) -> tuple[bool, str | None]:
    """Try to fill abstract from arXiv API via arxiv_id.
    Returns (success, error_tag).
    """
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


def enrich_abstracts(
    papers: list[dict[str, Any]],
    crossref_enabled: bool = True,
    arxiv_enabled: bool = True,
) -> tuple[int, int, int]:
    """Fill missing abstracts via fallback chain. Returns (crossref, arxiv, unavailable)."""
    cr_count = 0
    arxiv_count = 0
    unavailable = 0

    missing = [p for p in papers if not p.get("abstract") or p.get("abstract") == "" or p.get("abstract") == "[abstract unavailable]" or p.get("abstract", "").startswith("[error:")]
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

        # Layer 3: Mark unavailable (no source had it)
        if not paper.get("abstract"):
            paper["abstract"] = "[abstract unavailable]"
            unavailable += 1

    return cr_count, arxiv_count, unavailable


# ---------------------------------------------------------------------------
# Keyword scoring
# ---------------------------------------------------------------------------


def score_by_keywords(
    papers: list[dict[str, Any]], keywords: list[str]
) -> list[dict[str, Any]]:
    if not keywords:
        return papers
    kw_lower = [k.lower() for k in keywords]

    def _score(paper: dict[str, Any]) -> int:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
        return sum(1 for k in kw_lower if k in text)

    papers.sort(key=_score, reverse=True)
    return papers


# ---------------------------------------------------------------------------
# CSV read/write (merge-safe)
# ---------------------------------------------------------------------------


def read_existing_csv(path: str) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
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
    existing_human: dict[str, dict[str, str]],
) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    for paper in papers:
        row = {col: str(paper.get(col, "")) for col in CSV_COLUMNS}
        pid = row["paper_id"]
        if pid in existing_human:
            row["keep"] = existing_human[pid].get("keep", "")
            row["notes"] = existing_human[pid].get("notes", "")
        writer.writerow(row)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        f.write(buf.getvalue())
    os.replace(tmp_path, path)
    return len(papers)


def append_csv(
    new_papers: list[dict[str, Any]],
    path: str,
    seen_paper_ids: set[str],
) -> int:
    if not new_papers:
        return 0
    net_new = [p for p in new_papers if p["paper_id"] not in seen_paper_ids]
    if not net_new:
        return 0
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        for paper in net_new:
            row = {col: str(paper.get(col, "")) for col in CSV_COLUMNS}
            writer.writerow(row)
    return len(net_new)


# ---------------------------------------------------------------------------
# State update
# ---------------------------------------------------------------------------


def update_state(
    state: dict[str, Any],
    mode: str,
    new_papers: list[dict[str, Any]],
    config: dict[str, Any],
    effective_start: str,
    venue_stats: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z"
    new_ids = [p["paper_id"] for p in new_papers]
    seen = set(state.get("seen_paper_ids", []))
    seen.update(new_ids)
    state["seen_paper_ids"] = sorted(seen)

    if mode == "full":
        state["last_full_crawl"] = now
    else:
        state["last_incremental_crawl"] = now

    if venue_stats:
        state["crawled_venues"] = venue_stats

    state["crawl_history"].append({
        "date": now[:10],
        "mode": mode,
        "effective_start": effective_start,
        "effective_end": now[:10],
        "new_papers": len(new_papers),
        "total_unique": len(seen),
    })
    return state


# ---------------------------------------------------------------------------
# Update-mode helpers
# ---------------------------------------------------------------------------


def _compute_update_years(state: dict[str, Any], config: dict[str, Any]) -> tuple[int, int]:
    """Compute year range for incremental update with overlap."""
    overlap = config.get("update", {}).get("overlap_years", 1)
    end_year = datetime.now().year

    # Find latest crawled year
    crawled = state.get("crawled_venues", [])
    if crawled:
        max_year = max(v.get("year", 0) for v in crawled)
        start_year = max_year - overlap + 1
    else:
        start_year = int(config.get("date_range", {}).get("start", 2020))

    return start_year, end_year


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Survey Crawler v2: DBLP venue-based discovery + enrichment.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="Crawl papers and output CSV")
    crawl_parser.add_argument("--config", required=True, help="Path to config.yaml")
    crawl_parser.add_argument("--output", required=True, help="Output CSV path")
    crawl_parser.add_argument("--state", required=True, help="State JSON path")
    crawl_parser.add_argument(
        "--mode", choices=["full", "update"], default="full",
        help="Crawl mode (default: full)",
    )
    crawl_parser.add_argument(
        "--no-enrich", action="store_true",
        help="Skip all enrichment (S2 + Crossref + arXiv)",
    )
    crawl_parser.add_argument(
        "--no-s2", action="store_true",
        help="Skip S2 enrichment only",
    )

    enrich_parser = subparsers.add_parser("enrich", help="Enrich existing CSV (no DBLP fetch)")
    enrich_parser.add_argument("--input", required=True, help="Input CSV path")
    enrich_parser.add_argument("--output", required=True, help="Output CSV path (can be same as input)")
    enrich_parser.add_argument("--state", required=True, help="State JSON path")
    enrich_parser.add_argument(
        "--no-s2", action="store_true",
        help="Skip S2 enrichment only",
    )
    enrich_parser.add_argument(
        "--force", action="store_true",
        help="Re-enrich all papers (default: only enrich missing/error items)",
    )

    return parser


def crawl_main(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    state = load_state(args.state)

    # Header
    mode_label = "UPDATE" if args.mode == "update" else "FULL"
    print(f"\n{'='*60}")
    print(f"  Survey Crawler — {mode_label} mode")
    print(f"  Topic: {config.get('topic', 'unknown')}")
    print(f"  Venues: {', '.join(v['id'] for v in config.get('venues', []))}")
    print(f"  Years: {config.get('date_range', {}).get('start', '?')}–{config.get('date_range', {}).get('end', '?')}")
    print(f"{'='*60}\n")

    # Determine year range
    if args.mode == "update":
        start_year, end_year = _compute_update_years(state, config)
        print(f"  Update window: years {start_year}–{end_year}\n")
        config["date_range"] = {"start": start_year, "end": end_year}
        effective_start = str(start_year)
    else:
        effective_start = str(config.get("date_range", {}).get("start", ""))

    # ── Phase A: DBLP ──
    print("── Phase A: DBLP proceedings fetch ──")
    papers, fetch_failures = fetch_all_venues(config)
    print(f"  Result: {len(papers)} papers from DBLP")
    if fetch_failures:
        print(f"  WARNING: {len(fetch_failures)} venue×year fetches FAILED:")
        for f in fetch_failures:
            print(f"    - {f['venue']} {f['year']}: {f['error']}")
    print()

    if not papers:
        print("  No papers found. Check config venues and date_range.")
        return 0

    # Build venue stats
    venue_stats = []
    for venue in config.get("venues", []):
        for year in range(
            int(config["date_range"]["start"]),
            int(config["date_range"]["end"]) + 1,
        ):
            count = sum(
                1 for p in papers
                if p["venue"] == venue["id"] and p["year"] == str(year)
            )
            if count:
                venue_stats.append({
                    "venue": venue["id"],
                    "year": year,
                    "papers": count,
                    "crawled": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                })

    # ── Phase B: S2 enrichment ──
    enrich_cfg = config.get("enrichment", {})
    s2_enabled = enrich_cfg.get("s2", {}).get("enabled", True) and not args.no_s2 and not args.no_enrich

    print("── Phase B: S2 enrichment (via DOI) ──")
    if s2_enabled:
        eligible = sum(1 for p in papers if p.get("doi"))
        print(f"  Papers with DOI: {eligible}/{len(papers)}")
        enriched, s2_abstracts = enrich_from_s2(papers, enabled=True)
        print(f"  Result: {enriched} enriched, {s2_abstracts} abstracts from S2")
    else:
        print("  SKIPPED (--no-s2 or --no-enrich)")
    print()

    # ── Phase C: Abstract fallback ──
    cr_enabled = enrich_cfg.get("crossref", {}).get("enabled", True) and not args.no_enrich
    arxiv_enabled = enrich_cfg.get("arxiv", {}).get("enabled", True) and not args.no_enrich

    def _is_missing_abstract(p):
        ab = p.get("abstract", "")
        return not ab or ab == "[abstract unavailable]" or ab.startswith("[error:")

    missing = sum(1 for p in papers if _is_missing_abstract(p))
    have_abstract = len(papers) - missing

    print("── Phase C: Abstract fallback ──")
    print(f"  Abstracts status: {have_abstract} have, {missing} missing")
    if missing > 0 and (cr_enabled or arxiv_enabled):
        cr_count, arxiv_count, unavail = enrich_abstracts(
            papers, crossref_enabled=cr_enabled, arxiv_enabled=arxiv_enabled,
        )
        print(f"  Result: Crossref={cr_count}, arXiv={arxiv_count}, unavailable={unavail}")
    elif missing > 0:
        print(f"  SKIPPED (enrichment disabled)")
    else:
        print(f"  All abstracts already filled, nothing to do")
    print()

    # ── Phase D: Score + write ──
    print("── Phase D: Score + CSV write ──")
    keywords = config.get("keywords", [])
    papers = score_by_keywords(papers, keywords)
    print(f"  Sorted by keywords: {', '.join(keywords[:5])}{'...' if len(keywords) > 5 else ''}")

    if args.mode == "full":
        _, existing_human = read_existing_csv(args.output)
        preserved = sum(1 for pid in existing_human if any(p["paper_id"] == pid for p in papers))
        count = write_csv(papers, args.output, existing_human)
        print(f"  Written: {count} papers to {args.output}")
        if preserved:
            print(f"  Preserved: {preserved} existing keep/notes values")
    else:
        seen_ids = set(state.get("seen_paper_ids", []))
        count = append_csv(papers, args.output, seen_ids)
        print(f"  Appended: {count} new papers to {args.output}")

    # State update
    state = update_state(state, args.mode, papers, config, effective_start, venue_stats)
    if not state.get("topic_slug"):
        state["topic_slug"] = _slugify(config.get("topic", "unknown"))
    save_state(args.state, state)

    # ── Summary ──
    final_have_abstract = sum(1 for p in papers if p.get("abstract") and p["abstract"] != "[abstract unavailable]")
    final_unavail = sum(1 for p in papers if p.get("abstract") == "[abstract unavailable]")
    print(f"\n{'='*60}")
    print(f"  DONE — {len(papers)} papers total")
    print(f"  Abstracts: {final_have_abstract} available, {final_unavail} unavailable")
    print(f"  Output: {args.output}")
    print(f"  State:  {args.state}")
    if final_unavail > 0:
        print(f"\n  Next step: Open CSV in spreadsheet, set keep=yes/no/maybe,")
        print(f"  then run /survey-filter \"{config.get('topic', 'TOPIC')}\"")
    print(f"{'='*60}\n")

    return 0


def enrich_main(args: argparse.Namespace) -> int:
    """Enrich existing CSV with S2 + Crossref + arXiv. No DBLP fetch.
    By default, only processes papers with empty/error abstract or missing citation_count.
    Use --force to re-enrich everything.
    """
    rows, existing_human = read_existing_csv(args.input)
    if not rows:
        print(f"No papers found in {args.input}")
        return 1

    all_papers: list[dict[str, Any]] = [dict(r) for r in rows]

    # ── Classify papers ──
    def _needs_enrichment(p: dict) -> bool:
        """True if paper is missing abstract, has error abstract, or missing citation_count."""
        ab = p.get("abstract", "")
        if not ab or ab == "":
            return True
        if ab.startswith("[error:"):
            return True
        if ab == "[abstract unavailable]":
            return True
        cc = str(p.get("citation_count", ""))
        if not cc or cc in ("0", ""):
            return True
        return False

    if args.force:
        to_enrich = all_papers
        skipped = 0
    else:
        to_enrich = [p for p in all_papers if _needs_enrichment(p)]
        skipped = len(all_papers) - len(to_enrich)

    # ── Header ──
    print(f"\n{'='*60}")
    print(f"  Survey Crawler — ENRICH only")
    print(f"  Input:  {args.input}")
    print(f"  Total:  {len(all_papers)} papers")
    print(f"  To enrich: {len(to_enrich)} (skipped: {skipped} already complete)")
    if args.force:
        print(f"  Mode:   --force (re-enrich all)")
    if args.no_s2:
        print(f"  --no-s2: S2 enrichment disabled")
    print(f"{'='*60}\n")

    if not to_enrich:
        print("  Nothing to enrich. Use --force to re-enrich everything.\n")
        return 0

    # ── Phase B: S2 enrichment ──
    print("── Phase B: S2 enrichment (via DOI) ──")
    if not args.no_s2:
        eligible = sum(1 for p in to_enrich if p.get("doi"))
        print(f"  Papers with DOI: {eligible}/{len(to_enrich)}")
        enriched, s2_abstracts = enrich_from_s2(to_enrich, enabled=True)
        print(f"  Result: {enriched} enriched, {s2_abstracts} abstracts from S2")
    else:
        print("  SKIPPED (--no-s2)")
    print()

    # ── Phase C: Abstract fallback ──
    def _is_missing_abstract(p):
        ab = p.get("abstract", "")
        return not ab or ab == "[abstract unavailable]" or ab.startswith("[error:")

    missing = sum(1 for p in to_enrich if _is_missing_abstract(p))
    have_abstract = len(to_enrich) - missing

    print("── Phase C: Abstract fallback ──")
    print(f"  Abstracts status: {have_abstract} have, {missing} missing")
    if missing > 0:
        cr_count, arxiv_count, unavail = enrich_abstracts(
            to_enrich, crossref_enabled=True, arxiv_enabled=True,
        )
        print(f"  Result: Crossref={cr_count}, arXiv={arxiv_count}, unavailable={unavail}")
    else:
        print(f"  All abstracts already filled, nothing to do")
    print()

    # ── Merge back into all rows and write ──
    enriched_by_id = {p["paper_id"]: p for p in to_enrich}
    for row in all_papers:
        pid = row.get("paper_id", "")
        if pid in enriched_by_id:
            ep = enriched_by_id[pid]
            for col in CSV_COLUMNS:
                if col in HUMAN_COLUMNS:
                    continue
                new_val = str(ep.get(col, ""))
                old_val = row.get(col, "")
                # Only overwrite if new value is richer
                if new_val and (not old_val or new_val != old_val):
                    row[col] = new_val

    write_csv(all_papers, args.output, existing_human)
    print(f"  Written: {len(all_papers)} papers to {args.output}")

    # ── Summary ──
    def _count_abstracts(plist):
        have = sum(1 for p in plist
                   if p.get("abstract") and not p["abstract"].startswith("[")
                   and p["abstract"] != "[abstract unavailable]")
        errors = sum(1 for p in plist if p.get("abstract", "").startswith("[error:"))
        unavail = sum(1 for p in plist if p.get("abstract") == "[abstract unavailable]")
        empty = sum(1 for p in plist if not p.get("abstract"))
        return have, errors, unavail, empty

    have, errors, unavail, empty = _count_abstracts(all_papers)
    print(f"\n{'='*60}")
    print(f"  DONE — enriched {len(to_enrich)} papers")
    print(f"  Abstracts: {have} available | {errors} error | {unavail} unavailable | {empty} empty")
    if errors > 0:
        print(f"  Errors written to abstract column — search for '[error:' to find them")
    print(f"  Output: {args.output}")
    print(f"{'='*60}\n")

    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.command == "crawl":
            return crawl_main(args)
        if args.command == "enrich":
            return enrich_main(args)
        raise ValueError(f"Unknown command: {args.command}")
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
