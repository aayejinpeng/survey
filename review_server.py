#!/usr/bin/env python3
"""review_server.py — Local web server for reviewing scored papers.

Usage
-----
python3 review_server.py --csv data/topics/cpu-ai/scored-score-gte11.csv [--topic configs/topic-cpu-ai.yaml]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, parse_qs

# ---------------------------------------------------------------------------
# Data store
# ---------------------------------------------------------------------------

class PaperStore:
    """In-memory store backed by a CSV file."""

    COLUMNS = [
        "paper_id", "arxiv_id", "s2_paper_id", "title", "authors",
        "year", "venue", "abstract", "source", "categories",
        "citation_count", "url", "doi", "published_date", "crawled_date",
        "keep", "notes", "relevance_score", "matched_keywords", "relevance",
    ]

    def __init__(self, csv_path: str):
        self.csv_path = os.path.abspath(csv_path)
        self.papers: list[dict[str, Any]] = []
        self._load()

    def _load(self):
        with open(self.csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.papers.append(dict(row))
        print(f"Loaded {len(self.papers)} papers from {self.csv_path}")

    def get_papers(self) -> list[dict[str, Any]]:
        return self.papers

    def mark(self, paper_id: str, keep: str = "", tags: str = "") -> bool:
        for p in self.papers:
            if p.get("paper_id") == paper_id:
                if keep:
                    p["keep"] = keep
                if tags is not None:
                    p["notes"] = tags
                return True
        return False

    def save(self) -> int:
        """Write current state back to CSV (atomic)."""
        tmp_path = self.csv_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS, quoting=csv.QUOTE_ALL, extrasaction="ignore")
            writer.writeheader()
            for paper in self.papers:
                writer.writerow({col: str(paper.get(col, "")) for col in self.COLUMNS})
        os.replace(tmp_path, self.csv_path)
        print(f"Saved {len(self.papers)} papers to {self.csv_path}")
        return len(self.papers)


def load_topic_keywords(path: str) -> list[dict[str, Any]]:
    """Load keywords from topic config YAML."""
    if not path or not os.path.isfile(path):
        return []
    import yaml
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}
    keywords = config.get("keywords", [])
    result = []
    for kw in keywords:
        if isinstance(kw, str):
            result.append({"term": kw, "weight": 1})
        elif isinstance(kw, dict):
            result.append({"term": kw["term"], "weight": kw.get("weight", 1)})
    return result


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

_HTML_DIR = os.path.dirname(os.path.abspath(__file__))
store: PaperStore | None = None
keywords: list[dict[str, Any]] = []


class ReviewHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Quieter logging
        pass

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, path: str):
        with open(path, encoding="utf-8") as f:
            body = f.read().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            html_path = os.path.join(_HTML_DIR, "review.html")
            self._send_html(html_path)
        elif path == "/api/papers":
            self._send_json(store.get_papers())
        elif path == "/api/keywords":
            self._send_json(keywords)
        else:
            self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/mark":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            paper_id = body.get("paper_id", "")
            keep = body.get("keep", "")
            tags = body.get("tags", "")
            ok = store.mark(paper_id, keep, tags)
            self._send_json({"ok": ok})

        elif path == "/api/save":
            count = store.save()
            self._send_json({"ok": True, "count": count})
        else:
            self.send_error(404)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Paper review web server.")
    parser.add_argument("--csv", required=True, help="Path to scored CSV")
    parser.add_argument("--topic", default=None, help="Path to topic config YAML (for keyword highlighting)")
    parser.add_argument("--port", type=int, default=8088, help="Port (default: 8088)")
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    global store, keywords
    store = PaperStore(args.csv)
    keywords = load_topic_keywords(args.topic)

    if keywords:
        print(f"Loaded {len(keywords)} keywords for highlighting")

    server = HTTPServer(("0.0.0.0", args.port), ReviewHandler)
    url = f"http://localhost:{args.port}"
    print(f"\n  Paper Review Server: {url}")
    print(f"  CSV: {args.csv}")
    print(f"  Press Ctrl+C to stop\n")

    if not args.no_open:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
