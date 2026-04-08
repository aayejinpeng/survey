#!/usr/bin/env python3
"""s2_fetch.py — Semantic Scholar API client with batch support.

Optimized for the survey pipeline:
- Batch endpoint (POST /paper/batch): up to 500 papers per request
- Built-in rate limiter with Retry-After support
- Only exposes what the pipeline needs: batch fetch + single fetch
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_API_BASE = "https://api.semanticscholar.org/graph/v1"
_BATCH_MAX = 500

# S2 free tier: ~100 req / 5 min ≈ 1 req / 3s
# With API key: 1 req / s
_DEFAULT_RPS = 0.33
_KEYED_RPS = 1.0


# ---------------------------------------------------------------------------
# Rate limiter (token bucket)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, rps: float):
        self._interval = 1.0 / rps
        self._last = 0.0

    def wait(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last
        if elapsed < self._interval:
            time.sleep(self._interval - elapsed)
        self._last = time.monotonic()


# Module-level rate limiter (lazy init)
_limiter: _RateLimiter | None = None


def _get_limiter() -> _RateLimiter:
    global _limiter
    if _limiter is None:
        api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
        rps = _KEYED_RPS if api_key else _DEFAULT_RPS
        _limiter = _RateLimiter(rps)
    return _limiter


# ---------------------------------------------------------------------------
# Low-level request
# ---------------------------------------------------------------------------


def _headers() -> dict[str, str]:
    headers = {
        "User-Agent": "s2-survey/1.0",
        "Accept": "application/json",
    }
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip()
    if api_key:
        headers["x-api-key"] = api_key
    return headers


def _request(
    url: str,
    method: str = "GET",
    body: bytes | None = None,
    retries: int = 3,
    timeout: int = 30,
) -> dict[str, Any] | None:
    """HTTP request with 429 retry + Retry-After support. Returns parsed JSON or None on 404."""
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)

    for attempt in range(retries):
        _get_limiter().wait()

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))

        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None

            if exc.code == 429:
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else min(2 ** (attempt + 2), 60)
                key_info = ""
                if not os.getenv("SEMANTIC_SCHOLAR_API_KEY", "").strip():
                    key_info = " (no API key — set SEMANTIC_SCHOLAR_API_KEY)"
                print(f"    S2 429, waiting {wait:.0f}s (attempt {attempt+1}/{retries}){key_info}", file=sys.stderr)
                time.sleep(wait)
                continue

            if exc.code in (500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue

            body_text = ""
            try:
                body_text = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            raise RuntimeError(f"S2 HTTP {exc.code}: {body_text}") from exc

        except (urllib.error.URLError, OSError) as exc:
            if attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            raise RuntimeError(f"S2 network error: {exc}") from exc

    raise RuntimeError(f"S2 request failed after {retries} retries (429 rate limited)")


# ---------------------------------------------------------------------------
# Public API: single paper fetch
# ---------------------------------------------------------------------------


def get_paper(paper_id: str, fields: str = "") -> dict[str, Any] | None:
    """Fetch one paper by ID (DOI:xxx, ARXIV:xxx, CorpusId:xxx, etc).
    Returns parsed paper dict or None if not found.
    """
    if not fields:
        fields = "paperId,citationCount,abstract,externalIds,publicationDate,fieldsOfStudy"

    encoded = urllib.parse.quote(paper_id, safe="")
    url = f"{_API_BASE}/paper/{encoded}?fields={fields}"
    return _request(url)


# ---------------------------------------------------------------------------
# Public API: batch fetch (the key optimization)
# ---------------------------------------------------------------------------


def get_papers_batch(
    ids: list[str],
    fields: str = "",
) -> list[dict[str, Any] | None]:
    """Fetch multiple papers in one request via POST /paper/batch.

    S2 accepts up to 500 IDs per batch request. Automatically chunks
    larger lists.

    Args:
        ids: List of paper IDs (e.g. ["DOI:10.1109/...", "DOI:..."])
        fields: Comma-separated fields to request.

    Returns:
        List parallel to `ids` — each element is a paper dict or None (not found).
    """
    if not fields:
        fields = "paperId,citationCount,abstract,externalIds,publicationDate,fieldsOfStudy"

    if not ids:
        return []

    results: list[dict[str, Any] | None] = [None] * len(ids)

    for chunk_start in range(0, len(ids), _BATCH_MAX):
        chunk = ids[chunk_start : chunk_start + _BATCH_MAX]
        n = len(chunk)
        label = f"[{chunk_start+1}-{chunk_start+n}/{len(ids)}]"

        url = f"{_API_BASE}/paper/batch?fields={fields}"
        body = json.dumps({"ids": chunk}).encode("utf-8")

        data = _request(url, method="POST", body=body)
        if data is None:
            print(f"    {label} batch returned None", file=sys.stderr)
            continue

        if isinstance(data, list):
            for i, paper in enumerate(data):
                idx = chunk_start + i
                if idx < len(results):
                    results[idx] = paper
            found = sum(1 for p in data if p is not None)
            print(f"    {label} batch OK: {found}/{n} papers found", file=sys.stderr)
        else:
            print(f"    {label} unexpected response: {type(data)}", file=sys.stderr)

    return results


# ---------------------------------------------------------------------------
# CLI (for quick testing)
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Semantic Scholar fetch (batch-aware)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_paper = sub.add_parser("paper", help="Fetch single paper")
    p_paper.add_argument("id", help="Paper ID (DOI:xxx, ARXIV:xxx, etc.)")

    p_batch = sub.add_parser("batch", help="Fetch multiple papers")
    p_batch.add_argument("ids", nargs="+", help="Paper IDs")

    args = parser.parse_args(argv)

    try:
        if args.cmd == "paper":
            result = get_paper(args.id)
            print(json.dumps(result, ensure_ascii=False, indent=2))

        elif args.cmd == "batch":
            results = get_papers_batch(args.ids)
            for i, (pid, paper) in enumerate(zip(args.ids, results)):
                title = paper.get("title", "(not found)") if paper else "(not found)"
                cc = paper.get("citationCount", "?") if paper else "?"
                print(f"  [{i+1}] {pid}")
                print(f"       title: {title}")
                print(f"       citations: {cc}")
            found = sum(1 for r in results if r is not None)
            print(f"\n  Found: {found}/{len(args.ids)}")

        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
