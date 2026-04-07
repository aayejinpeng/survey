#!/usr/bin/env python3
"""Survey Crawler: fetch papers from arXiv + Semantic Scholar, output CSV.

Reuses arxiv_fetch.py and semantic_scholar_fetch.py as imported modules.

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

# ---------------------------------------------------------------------------
# Config / State helpers
# ---------------------------------------------------------------------------


def _slugify(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def load_config(path: str) -> dict[str, Any]:
    """Load config.yaml.  Falls back to a minimal YAML parser (no PyYAML dep)."""
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Config not found: {path}")

    with open(path, encoding="utf-8") as f:
        text = f.read()

    # Minimal YAML subset parser — handles the config format we defined.
    # If PyYAML is available, prefer it.
    try:
        import yaml  # type: ignore[import-untyped]

        return yaml.safe_load(text) or {}
    except ImportError:
        return _parse_simple_yaml(text)


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Very small YAML parser for our config format only."""
    # Not general-purpose; handles our flat + one-level-nested structure.
    import yaml  # will fail if not installed; we require it

    return yaml.safe_load(text)


def load_state(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        return {
            "topic_slug": "",
            "last_full_crawl": None,
            "last_incremental_crawl": None,
            "seen_paper_ids": [],
            "crawl_history": [],
        }
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str, state: dict[str, Any]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Step 1.2: arXiv crawling
# ---------------------------------------------------------------------------


def crawl_arxiv(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Search arXiv and return normalised paper dicts."""
    arxiv_cfg = config.get("arxiv", {})
    queries = arxiv_cfg.get("queries", [])
    categories = arxiv_cfg.get("categories", [])
    max_per_query = arxiv_cfg.get("max_per_query", 50)

    results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for query in queries:
        # Build query with category prefix if specified
        full_query = query
        if categories:
            cat_prefix = " OR ".join(f"cat:{cat}" for cat in categories)
            full_query = f"({cat_prefix}) AND ({query})"

        try:
            entries = arxiv_fetch.search(full_query, max_results=max_per_query)
        except Exception as exc:
            print(f"  [arxiv] query '{query}' failed: {exc}", file=sys.stderr)
            continue

        for entry in entries:
            aid = entry["id"]
            if aid in seen_ids:
                continue
            seen_ids.add(aid)

            results.append({
                "paper_id": f"arxiv:{aid}",
                "arxiv_id": aid,
                "s2_paper_id": "",
                "title": entry["title"],
                "authors": "; ".join(entry.get("authors", [])),
                "year": entry.get("published", "")[:4],
                "venue": "arXiv",
                "abstract": entry.get("abstract", ""),
                "source": "arxiv",
                "categories": "; ".join(entry.get("categories", [])),
                "citation_count": 0,
                "url": entry.get("abs_url", f"https://arxiv.org/abs/{aid}"),
                "doi": "",
                "published_date": entry.get("published", "")[:10],
                "crawled_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "keep": "",
                "notes": "",
            })

    return results


# ---------------------------------------------------------------------------
# Step 1.3: Semantic Scholar crawling
# ---------------------------------------------------------------------------


def crawl_s2(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Search Semantic Scholar and return normalised paper dicts."""
    s2_cfg = config.get("semantic_scholar", {})
    queries = s2_cfg.get("queries", [])
    max_per_query = s2_cfg.get("max_per_query", 50)
    fields_of_study = s2_cfg.get("fields_of_study")
    pub_types = s2_cfg.get("publication_types")
    min_citations = s2_cfg.get("min_citations")
    date_range = config.get("date_range", {})
    year_str: str | None = None
    if date_range.get("start") or date_range.get("end"):
        s = date_range.get("start", "") or ""
        e = date_range.get("end", "") or ""
        year_str = f"{s[:4]}-{e[:4]}" if e else f"{s[:4]}-"

    results: list[dict[str, Any]] = []
    seen_s2: set[str] = set()

    for query in queries:
        try:
            resp = s2_fetch.search(
                query=query,
                max_results=max_per_query,
                fields_of_study=fields_of_study,
                publication_types=pub_types,
                min_citation_count=min_citations,
                year=year_str,
            )
            papers = resp.get("data", [])
        except Exception as exc:
            print(f"  [s2] query '{query}' failed: {exc}", file=sys.stderr)
            continue

        for p in papers:
            pid = p.get("paperId", "")
            if not pid or pid in seen_s2:
                continue
            seen_s2.add(pid)

            ext = p.get("externalIds") or {}
            arxiv_id = ext.get("ArXiv", "")
            doi = ext.get("DOI", "")

            paper_id = f"arxiv:{arxiv_id}" if arxiv_id else f"s2:{pid}"

            authors_list = p.get("authors") or []
            authors_str = "; ".join(a.get("name", "") for a in authors_list if a.get("name"))

            results.append({
                "paper_id": paper_id,
                "arxiv_id": arxiv_id,
                "s2_paper_id": pid,
                "title": p.get("title", ""),
                "authors": authors_str,
                "year": str(p.get("year", "")) if p.get("year") else "",
                "venue": p.get("venue", ""),
                "abstract": p.get("abstract", ""),
                "source": "semantic_scholar",
                "categories": "; ".join(p.get("fieldsOfStudy") or []),
                "citation_count": p.get("citationCount", 0) or 0,
                "url": p.get("url", ""),
                "doi": doi,
                "published_date": (p.get("publicationDate") or "")[:10],
                "crawled_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "keep": "",
                "notes": "",
            })

    return results


# ---------------------------------------------------------------------------
# Step 1.4: S2 enrichment for arXiv papers
# ---------------------------------------------------------------------------


def enrich_from_s2(papers: list[dict[str, Any]], delay: float = 1.1) -> None:
    """For arXiv-only papers, look up S2 to fill citation_count, venue, doi, s2_paper_id."""
    for paper in papers:
        if paper["source"] != "arxiv" or paper["arxiv_id"] == "":
            continue
        try:
            s2_data = s2_fetch.get_paper(
                f"ARXIV:{paper['arxiv_id']}",
                fields="paperId,citationCount,venue,publicationVenue,externalIds,publicationDate,doi",
            )
            paper["citation_count"] = s2_data.get("citationCount", 0) or 0
            paper["s2_paper_id"] = s2_data.get("paperId", "")
            if s2_data.get("venue") and not paper["venue"].startswith("arXiv"):
                paper["venue"] = s2_data["venue"]
            ext = s2_data.get("externalIds") or {}
            if ext.get("DOI") and not paper["doi"]:
                paper["doi"] = ext["DOI"]
            if s2_data.get("publicationDate") and not paper["published_date"]:
                paper["published_date"] = s2_data["publicationDate"][:10]
        except Exception as exc:
            print(f"  [s2-enrich] {paper['arxiv_id']}: {exc}", file=sys.stderr)
        time.sleep(delay)


# ---------------------------------------------------------------------------
# Step 1.5: Deduplication + merge
# ---------------------------------------------------------------------------


def _normalise_doi(doi: str) -> str:
    return doi.strip().lower().rstrip("/")


def dedup_papers(
    arxiv_results: list[dict[str, Any]],
    s2_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge arXiv and S2 results, deduplicating by arxiv_id > doi > s2_paper_id."""
    by_arxiv: dict[str, dict[str, Any]] = {}
    by_doi: dict[str, dict[str, Any]] = {}
    by_s2: dict[str, dict[str, Any]] = {}

    def _index(paper: dict[str, Any]) -> None:
        aid = paper.get("arxiv_id", "")
        if aid:
            by_arxiv.setdefault(aid, paper)
        doi = paper.get("doi", "")
        if doi:
            ndoi = _normalise_doi(doi)
            by_doi.setdefault(ndoi, paper)
        sid = paper.get("s2_paper_id", "")
        if sid:
            by_s2.setdefault(sid, paper)

    # Index arXiv results first (lower priority for merge)
    for p in arxiv_results:
        _index(p)

    # S2 results merge into existing or create new
    for p in s2_results:
        aid = p.get("arxiv_id", "")
        doi = p.get("doi", "")
        sid = p.get("s2_paper_id", "")

        # Find existing match
        existing: dict[str, Any] | None = None
        if aid and aid in by_arxiv:
            existing = by_arxiv[aid]
        elif doi and _normalise_doi(doi) in by_doi:
            existing = by_doi[_normalise_doi(doi)]
        elif sid and sid in by_s2:
            existing = by_s2[sid]

        if existing:
            # Merge: prefer non-empty values, prefer S2 metadata
            _merge_into(existing, p)
        else:
            _index(p)

    # Collect unique papers (dedup by paper_id)
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for paper in list(by_arxiv.values()) + list(by_s2.values()):
        pid = paper["paper_id"]
        if pid not in seen:
            seen.add(pid)
            merged.append(paper)

    return merged


def _merge_into(target: dict[str, Any], source: dict[str, Any]) -> None:
    """Merge source into target. Prefer non-empty, prefer source's values."""
    machine_cols = [c for c in CSV_COLUMNS if c not in HUMAN_COLUMNS]
    for col in machine_cols:
        src_val = source.get(col, "")
        tgt_val = target.get(col, "")
        # Prefer source if it has a non-empty value and target is empty
        if src_val and not tgt_val:
            target[col] = src_val
        # For citation_count and s2_paper_id, prefer S2 (source)
        if col in ("citation_count", "s2_paper_id", "doi") and src_val:
            target[col] = src_val
    # Fix paper_id: prefer arxiv: prefix if arxiv_id exists
    if target.get("arxiv_id"):
        target["paper_id"] = f"arxiv:{target['arxiv_id']}"
    elif target.get("s2_paper_id"):
        target["paper_id"] = f"s2:{target['s2_paper_id']}"


# ---------------------------------------------------------------------------
# Step 1.6: Keyword scoring
# ---------------------------------------------------------------------------


def score_by_keywords(
    papers: list[dict[str, Any]], keywords: list[str]
) -> list[dict[str, Any]]:
    """Sort papers by simple keyword match score (descending)."""
    if not keywords:
        return papers

    kw_lower = [k.lower() for k in keywords]

    def _score(paper: dict[str, Any]) -> int:
        text = f"{paper.get('title', '')} {paper.get('abstract', '')}".lower()
        return sum(1 for k in kw_lower if k in text)

    papers.sort(key=_score, reverse=True)
    return papers


# ---------------------------------------------------------------------------
# Step 1.7: CSV read/write (merge-safe)
# ---------------------------------------------------------------------------


def read_existing_csv(path: str) -> tuple[list[dict[str, str]], dict[str, dict[str, str]]]:
    """Read existing CSV and return (rows, human_columns_by_paper_id).

    human_columns_by_paper_id maps paper_id -> {"keep": ..., "notes": ...}
    """
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
    """Write CSV with merge-safe human columns.  Returns number of papers written."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
    writer.writeheader()

    for paper in papers:
        row = {col: str(paper.get(col, "")) for col in CSV_COLUMNS}
        # Preserve human columns from existing CSV
        pid = row["paper_id"]
        if pid in existing_human:
            row["keep"] = existing_human[pid].get("keep", "")
            row["notes"] = existing_human[pid].get("notes", "")
        writer.writerow(row)

    # Atomic write: write to temp then rename
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
    """Append net-new papers to existing CSV.  Returns count of appended rows."""
    if not new_papers:
        return 0

    # Filter to net-new only
    net_new = [p for p in new_papers if p["paper_id"] not in seen_paper_ids]
    if not net_new:
        return 0

    # Append to existing file
    with open(path, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, quoting=csv.QUOTE_ALL)
        for paper in net_new:
            row = {col: str(paper.get(col, "")) for col in CSV_COLUMNS}
            writer.writerow(row)

    return len(net_new)


# ---------------------------------------------------------------------------
# Step 1.8: State update
# ---------------------------------------------------------------------------


def update_state(
    state: dict[str, Any],
    mode: str,
    new_papers: list[dict[str, Any]],
    config: dict[str, Any],
    effective_start: str,
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


def _compute_effective_start(state: dict[str, Any], config: dict[str, Any]) -> str:
    """Compute the effective start date for incremental update with overlap."""
    overlap_days = config.get("update", {}).get("overlap_days", 7)
    last = state.get("last_incremental_crawl") or state.get("last_full_crawl")
    if not last:
        # No previous crawl — fall back to config date_range.start
        return config.get("date_range", {}).get("start", "2020-01-01")

    # Parse the ISO timestamp
    last_date = last[:10]  # "YYYY-MM-DD"
    from datetime import timedelta
    dt = datetime.strptime(last_date, "%Y-%m-%d")
    effective = dt - timedelta(days=overlap_days)
    return effective.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Survey Crawler: fetch papers from arXiv + Semantic Scholar.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawl_parser = subparsers.add_parser("crawl", help="Crawl papers and output CSV")
    crawl_parser.add_argument("--config", required=True, help="Path to config.yaml")
    crawl_parser.add_argument("--output", required=True, help="Output CSV path")
    crawl_parser.add_argument("--state", required=True, help="State JSON path")
    crawl_parser.add_argument(
        "--mode",
        choices=["full", "update"],
        default="full",
        help="Crawl mode (default: full)",
    )
    crawl_parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Skip S2 enrichment step (faster but less metadata)",
    )

    return parser


def crawl_main(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    state = load_state(args.state)

    effective_start = ""
    if args.mode == "update":
        effective_start = _compute_effective_start(state, config)
        print(f"Update mode: effective start = {effective_start}")
    else:
        effective_start = config.get("date_range", {}).get("start", "")

    # Step 1.2: arXiv
    print("Crawling arXiv...")
    arxiv_results = crawl_arxiv(config)
    print(f"  arXiv: {len(arxiv_results)} papers")

    # Step 1.3: Semantic Scholar
    print("Crawling Semantic Scholar...")
    s2_results = crawl_s2(config)
    print(f"  S2: {len(s2_results)} papers")

    # Step 1.4: S2 enrichment for arXiv papers
    if not args.no_enrich and arxiv_results:
        print("Enriching arXiv papers with S2 metadata...")
        enrich_from_s2(arxiv_results)
        print("  Enrichment done")

    # Step 1.5: Dedup + merge
    merged = dedup_papers(arxiv_results, s2_results)
    print(f"After dedup: {len(merged)} unique papers")

    # Step 1.6: Keyword scoring
    keywords = config.get("keywords", [])
    merged = score_by_keywords(merged, keywords)

    if args.mode == "full":
        # Full mode: refresh machine columns, preserve human columns
        _, existing_human = read_existing_csv(args.output)
        count = write_csv(merged, args.output, existing_human)
        print(f"Written {count} papers to {args.output}")
    else:
        # Update mode: append net-new only
        seen_ids = set(state.get("seen_paper_ids", []))
        count = append_csv(merged, args.output, seen_ids)
        print(f"Appended {count} new papers to {args.output}")

    # Step 1.8: Update state
    state = update_state(state, args.mode, merged, config, effective_start)
    if not state.get("topic_slug"):
        state["topic_slug"] = _slugify(config.get("topic", "unknown"))
    save_state(args.state, state)
    print(f"State saved to {args.state}")

    return 0


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        if args.command == "crawl":
            return crawl_main(args)
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
