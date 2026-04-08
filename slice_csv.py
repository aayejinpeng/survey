#!/usr/bin/env python3
"""slice_csv.py — Extract a subset of a scored CSV by score threshold or top-N.

Works on any scored CSV that has a `relevance_score` column.

Usage
-----
# Extract papers with score >= 11
python3 slice_csv.py --input data/topics/cpu-ai/scored.csv --min-score 11

# Top 30 papers
python3 slice_csv.py --input data/topics/cpu-ai/scored.csv --top 30

# Custom output path
python3 slice_csv.py --input data/topics/cpu-ai/scored.csv --min-score 11 --output data/topics/cpu-ai/high11.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path


def slice_csv(
    input_path: str,
    output_path: str | None = None,
    min_score: int = 0,
    top_n: int = 0,
) -> int:
    if not os.path.isfile(input_path):
        print(f"Error: {input_path} not found", file=sys.stderr)
        return 1

    rows: list[dict[str, str]] = []
    with open(input_path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    if "relevance_score" not in (fieldnames or []):
        print("Error: no `relevance_score` column found", file=sys.stderr)
        return 1

    # Filter
    if min_score > 0:
        result = [r for r in rows if int(r.get("relevance_score", 0)) >= min_score]
        print(f"Score >= {min_score}: {len(result)}/{len(rows)} papers")
    elif top_n > 0:
        result = rows[:top_n]
        print(f"Top {top_n}: {len(result)} papers")
    else:
        print("Error: specify --min-score or --top", file=sys.stderr)
        return 1

    if not result:
        print("No papers matched.")
        return 0

    # Determine output path
    if output_path is None:
        base = os.path.splitext(input_path)[0]
        if min_score > 0:
            suffix = f"score-gte{min_score}"
        else:
            suffix = f"top{top_n}"
        output_path = f"{base}-{suffix}.csv"

    # Write
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        for row in result:
            writer.writerow(row)
    os.replace(tmp_path, output_path)

    print(f"Output: {output_path} ({len(result)} papers)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Slice a scored CSV by score or top-N.")
    parser.add_argument("--input", required=True, help="Input scored CSV")
    parser.add_argument("--output", default=None, help="Output path (auto-generated if omitted)")
    parser.add_argument("--min-score", type=int, default=0, help="Minimum relevance_score")
    parser.add_argument("--top", type=int, default=0, help="Take top N papers")

    args = parser.parse_args()
    return slice_csv(args.input, args.output, args.min_score, args.top)


if __name__ == "__main__":
    sys.exit(main())
