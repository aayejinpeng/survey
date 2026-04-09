#!/usr/bin/env python3
"""export_dois.py — Export DOIs of kept papers as clickable download links.

Reads a scored CSV (typically the slice output with keep tags), extracts papers
marked as "keep", and writes DOI links to a text file — one per line, ready to
click and download.

Usage
-----
python3 export_dois.py --input data/topics/cpu-ai/scored-score-gte11.csv

# Custom output path
python3 export_dois.py --input data/topics/cpu-ai/scored-score-gte11.csv --output my-dois.txt

# Custom tag filter (default: keep)
python3 export_dois.py --input data/topics/cpu-ai/scored-score-gte11.csv --tag core
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path


def export_dois(
    input_path: str,
    output_path: str | None = None,
    tag: str = "keep",
) -> int:
    if not os.path.isfile(input_path):
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    with open(input_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # Filter by tag and DOI presence
    matched = [
        r for r in rows
        if r.get("keep", "").strip().lower() == tag.lower()
        and r.get("doi", "").strip()
    ]

    missing_doi = [
        r for r in rows
        if r.get("keep", "").strip().lower() == tag.lower()
        and not r.get("doi", "").strip()
    ]

    print(f"Papers tagged '{tag}': {len(matched)} with DOI, {len(missing_doi)} without DOI")

    if not matched:
        print("No papers to export.")
        return 0

    # Default output path: same dir as input, doi-list.txt
    if output_path is None:
        base_dir = os.path.dirname(input_path)
        output_path = os.path.join(base_dir, "doi-list.txt")

    # Write DOI links
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for row in matched:
            doi = row["doi"].strip()
            title = row.get("title", "").strip()
            f.write(f"https://doi.org/{doi}\n")
    os.replace(tmp_path, output_path)

    print(f"Output: {output_path} ({len(matched)} links)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export DOIs of kept papers as clickable download links."
    )
    parser.add_argument("--input", required=True, help="Input scored CSV with keep column")
    parser.add_argument("--output", default=None, help="Output file (default: <input_dir>/doi-list.txt)")
    parser.add_argument("--tag", default="keep", help="Tag to filter (default: keep)")

    args = parser.parse_args()
    return export_dois(args.input, args.output, args.tag)


if __name__ == "__main__":
    sys.exit(main())
