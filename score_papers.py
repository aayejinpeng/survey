#!/usr/bin/env python3
"""Score enriched papers by topic keywords with weighted matching.

Reads enriched CSV(s), applies optional venue/year filters, computes relevance
scores using weighted keywords, and outputs a scored CSV with extra columns.

Usage
-----
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

python3 score_papers.py \
    --input data/enriched/micro-2024.csv \
    --topic-config configs/topic-cpu-ai.yaml \
    --output data/topics/cpu-ai/scored.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

def load_topic_config(path: str) -> dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Topic config not found: {path}")
    import yaml  # type: ignore[import-untyped]
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _parse_keywords(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse keywords from config. Supports both list-of-strings and list-of-dicts."""
    raw = config.get("keywords", [])
    result = []
    for kw in raw:
        if isinstance(kw, str):
            result.append({"term": kw, "weight": 1})
        elif isinstance(kw, dict):
            result.append({
                "term": kw["term"],
                "weight": kw.get("weight", 1),
            })
    return result


# ---------------------------------------------------------------------------
# CSV I/O
# ---------------------------------------------------------------------------

ENRICHED_COLUMNS = [
    "paper_id", "arxiv_id", "s2_paper_id", "title", "authors",
    "year", "venue", "abstract", "source", "categories",
    "citation_count", "url", "doi", "published_date", "crawled_date",
    "keep", "notes",
]

SCORED_EXTRA_COLUMNS = ["relevance_score", "matched_keywords", "relevance"]

SCORED_COLUMNS = ENRICHED_COLUMNS + SCORED_EXTRA_COLUMNS


def read_csv(path: str) -> list[dict[str, str]]:
    rows = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def read_all_csvs(paths: list[str]) -> tuple[list[dict[str, str]], int]:
    """Read and merge CSVs by paper_id (first occurrence wins)."""
    seen_ids: set[str] = set()
    merged: list[dict[str, str]] = []
    file_count = 0
    for p in paths:
        if not os.path.isfile(p):
            print(f"  SKIP: {p} (not found)", file=sys.stderr)
            continue
        rows = read_csv(p)
        file_count += 1
        for row in rows:
            pid = row.get("paper_id", "")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                merged.append(row)
    return merged, file_count


def write_scored_csv(papers: list[dict[str, Any]], path: str) -> int:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    buf_rows = 0
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SCORED_COLUMNS, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for paper in papers:
            row = {col: str(paper.get(col, "")) for col in SCORED_COLUMNS}
            writer.writerow(row)
            buf_rows += 1
    os.replace(tmp_path, path)
    return buf_rows


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def apply_filters(
    papers: list[dict[str, str]],
    config: dict[str, Any],
) -> list[dict[str, str]]:
    """Apply venue and year filters if configured."""
    result = list(papers)

    # Venue filter
    filter_venues = config.get("filter_venues")
    if filter_venues:
        venues_set = {v.upper() for v in filter_venues}
        result = [p for p in result if p.get("venue", "").upper() in venues_set]

    # Year filter
    filter_years = config.get("filter_years")
    if filter_years:
        start = int(filter_years.get("start", 0))
        end = int(filter_years.get("end", 9999))
        result = [
            p for p in result
            if start <= int(p.get("year", "0") or "0") <= end
        ]

    return result


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _build_pattern(term: str) -> re.Pattern[str]:
    """Build a word-boundary regex for a keyword term.

    Handles multi-word terms (e.g. "matrix extension") by requiring word
    boundaries only at the outer edges.  Hyphens and other non-word chars
    inside the term are treated as literal characters.
    """
    escaped = re.escape(term)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def score_paper(
    paper: dict[str, str],
    keywords: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    """Score a single paper. Returns (score, matched_keywords).

    Uses word-boundary matching so that e.g. "IME" does not match "intermediate",
    and "MX" does not match "matrix".
    """
    text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
    score = 0
    matched = []
    for kw in keywords:
        pattern = _build_pattern(kw["term"])
        if pattern.search(text):
            score += kw["weight"]
            matched.append(kw["term"])
    return score, matched


RELEVANCE_THRESHOLDS = [
    (10, "High"),
    (5, "Medium"),
    (1, "Low"),
]


def relevance_label(score: int) -> str:
    for threshold, label in RELEVANCE_THRESHOLDS:
        if score >= threshold:
            return label
    return "None"


def score_all_papers(
    papers: list[dict[str, str]],
    keywords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Score all papers and add relevance columns. Sort by score descending."""
    scored = []
    for paper in papers:
        sc, matched = score_paper(paper, keywords)
        p = dict(paper)
        p["relevance_score"] = sc
        p["matched_keywords"] = ", ".join(matched)
        p["relevance"] = relevance_label(sc)
        scored.append(p)
    scored.sort(key=lambda p: p["relevance_score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def find_csv_files(input_dir: str) -> list[str]:
    """Find all CSV files in a directory, sorted."""
    d = Path(input_dir)
    if not d.is_dir():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    return sorted(str(f) for f in d.glob("*.csv"))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score enriched papers by topic keywords.",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--input-dir",
        help="Directory of enriched CSV files (merged)",
    )
    input_group.add_argument(
        "--input",
        nargs="+",
        help="One or more enriched CSV files",
    )

    parser.add_argument(
        "--topic-config",
        required=True,
        help="Path to topic config YAML",
    )

    output_group = parser.add_mutually_exclusive_group(required=True)
    output_group.add_argument(
        "--output-dir",
        help="Output directory (writes scored.csv inside)",
    )
    output_group.add_argument(
        "--output",
        help="Direct output file path",
    )

    parser.add_argument(
        "--min-relevance",
        choices=["Low", "Medium", "High"],
        default=None,
        help="Minimum relevance level to include in output",
    )

    return parser


RELEVANCE_ORDER = {"None": 0, "Low": 1, "Medium": 2, "High": 3}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    # Load config
    config = load_topic_config(args.topic_config)
    keywords = _parse_keywords(config)
    topic = config.get("topic", "unknown")
    keyword_terms = [kw["term"] for kw in keywords]

    # Resolve input files
    if args.input_dir:
        csv_files = find_csv_files(args.input_dir)
    else:
        csv_files = args.input

    if not csv_files:
        print("No input CSV files found.")
        return 1

    # Read and merge
    papers, file_count = read_all_csvs(csv_files)
    print(f"Loaded: {len(papers)} papers from {file_count} files")

    # Filter
    before_filter = len(papers)
    papers = apply_filters(papers, config)
    after_filter = len(papers)
    if before_filter != after_filter:
        print(f"After venue/year filter: {after_filter} papers (removed {before_filter - after_filter})")
    else:
        print(f"After venue/year filter: {after_filter} papers")

    # Score
    print(f"Scoring with {len(keywords)} keywords: {', '.join(keyword_terms[:6])}{'...' if len(keyword_terms) > 6 else ''}")
    scored = score_all_papers(papers, keywords)

    # Print top papers
    print(f"\nTop papers:")
    for p in scored[:10]:
        if p["relevance_score"] > 0:
            print(f"  [score={p['relevance_score']}] {p['title'][:80]}")
        else:
            break

    # Distribution
    dist = {"High": 0, "Medium": 0, "Low": 0, "None": 0}
    for p in scored:
        dist[p["relevance"]] += 1
    print(f"\nDistribution:")
    for threshold, label in RELEVANCE_THRESHOLDS:
        print(f"  {label:6s}  {dist[label]:>4} papers (score >= {threshold})")
    print(f"  {'None':6s}  {dist['None']:>4} papers (score = 0)")

    # Apply min-relevance filter for output
    if args.min_relevance:
        min_level = RELEVANCE_ORDER[args.min_relevance]
        scored = [p for p in scored if RELEVANCE_ORDER[p["relevance"]] >= min_level]
        print(f"\nAfter --min-relevance {args.min_relevance}: {len(scored)} papers")

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        slug = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-") if topic != "unknown" else "scored"
        output_path = os.path.join(args.output_dir, "scored.csv")

    # Write scored.csv
    count = write_scored_csv(scored, output_path)
    print(f"\nOutput: {output_path} ({count} papers)")

    # Write top-N CSVs (only papers with score > 0)
    relevant = [p for p in scored if p["relevance_score"] > 0]
    output_dir = os.path.dirname(output_path)
    for n in (10, 50, 100):
        top_n = relevant[:n]
        if not top_n:
            break
        top_path = os.path.join(output_dir, f"top{n}.csv")
        n_count = write_scored_csv(top_n, top_path)
        print(f"Output: {top_path} ({n_count} papers)")

    return 0


if __name__ == "__main__":
    import re  # noqa: ensure available for slug
    sys.exit(main())
