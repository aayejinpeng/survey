#!/usr/bin/env python3
"""Unit tests for survey_crawler.py v2 — DBLP + enrichment pipeline.

No external API calls. Tests internal logic only.
"""

import csv
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from survey_crawler import (
    CSV_COLUMNS,
    HUMAN_COLUMNS,
    _slugify,
    _clean_crossref_abstract,
    enrich_from_s2,
    enrich_abstracts,
    score_by_keywords,
    update_state,
    write_csv,
    append_csv,
    read_existing_csv,
    _compute_update_years,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

MOCK_PAPERS = [
    {
        "paper_id": "doi:10.1109/ISCA.2024.001",
        "arxiv_id": "2401.12345",
        "s2_paper_id": "",
        "title": "CPU Matrix Extension for AI Inference",
        "authors": "Alice Smith; Bob Jones",
        "year": "2024",
        "venue": "ISCA",
        "abstract": "We propose a CPU matrix extension for efficient AI inference.",
        "source": "dblp",
        "categories": "",
        "citation_count": 0,
        "url": "https://doi.org/10.1109/ISCA.2024.001",
        "doi": "10.1109/ISCA.2024.001",
        "published_date": "2024-01-01",
        "crawled_date": "2026-04-08",
        "keep": "",
        "notes": "",
    },
    {
        "paper_id": "doi:10.1145/MICRO.2024.002",
        "arxiv_id": "",
        "s2_paper_id": "",
        "title": "Intel AMX Performance Characterization",
        "authors": "Carol Lee; David Wang",
        "year": "2024",
        "venue": "MICRO",
        "abstract": "",
        "source": "dblp",
        "categories": "",
        "citation_count": 0,
        "url": "https://doi.org/10.1145/MICRO.2024.002",
        "doi": "10.1145/MICRO.2024.002",
        "published_date": "2024-01-01",
        "crawled_date": "2026-04-08",
        "keep": "",
        "notes": "",
    },
    {
        "paper_id": "doi:10.1109/HPCA.2024.003",
        "arxiv_id": "2403.56789",
        "s2_paper_id": "",
        "title": "RISC-V Tensor Unit Design",
        "authors": "Eve Chen",
        "year": "2024",
        "venue": "HPCA",
        "abstract": "",
        "source": "dblp",
        "categories": "",
        "citation_count": 0,
        "url": "https://doi.org/10.1109/HPCA.2024.003",
        "doi": "10.1109/HPCA.2024.003",
        "published_date": "2024-01-01",
        "crawled_date": "2026-04-08",
        "keep": "",
        "notes": "",
    },
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_slugify():
    assert _slugify("CPU AI acceleration") == "cpu-ai-acceleration"
    assert _slugify("RISC-V tensor unit!") == "risc-v-tensor-unit"
    print("PASS: _slugify")


def test_csv_write_preserves_human_columns():
    """Full rerun preserves keep/notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")

        # First write
        write_csv(MOCK_PAPERS, csv_path, {})

        # Simulate user editing
        _, human = read_existing_csv(csv_path)
        human["doi:10.1109/ISCA.2024.001"] = {"keep": "yes", "notes": "important"}
        human["doi:10.1145/MICRO.2024.002"] = {"keep": "no", "notes": ""}

        # Re-write with machine column changed
        updated = list(MOCK_PAPERS)
        updated[0]["title"] = "UPDATED TITLE"
        write_csv(updated, csv_path, human)

        rows, human2 = read_existing_csv(csv_path)
        first = next(r for r in rows if r["paper_id"] == "doi:10.1109/ISCA.2024.001")
        assert first["keep"] == "yes"
        assert first["notes"] == "important"
        assert first["title"] == "UPDATED TITLE"

        second = next(r for r in rows if r["paper_id"] == "doi:10.1145/MICRO.2024.002")
        assert second["keep"] == "no"
        print("PASS: csv_write_preserves_human_columns")


def test_append_only_new():
    """Update mode only appends net-new papers."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        write_csv(MOCK_PAPERS[:2], csv_path, {})

        seen = {"doi:10.1109/ISCA.2024.001", "doi:10.1145/MICRO.2024.002"}
        count = append_csv(MOCK_PAPERS, csv_path, seen)
        assert count == 1, f"Expected 1 new, got {count}"

        rows, _ = read_existing_csv(csv_path)
        assert len(rows) == 3
        print("PASS: append_only_new")


def test_idempotent_update():
    """Second update with same data adds 0."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        write_csv(MOCK_PAPERS[:2], csv_path, {})

        seen = {"doi:10.1109/ISCA.2024.001", "doi:10.1145/MICRO.2024.002"}
        append_csv([MOCK_PAPERS[2]], csv_path, seen)
        seen.add("doi:10.1109/HPCA.2024.003")

        count2 = append_csv([MOCK_PAPERS[2]], csv_path, seen)
        assert count2 == 0
        print("PASS: idempotent_update")


def test_keyword_scoring():
    scored = score_by_keywords(list(MOCK_PAPERS), ["AMX", "Intel"])
    assert "AMX" in scored[0]["title"] or "Intel" in scored[0]["title"]
    print("PASS: keyword_scoring")


def test_state_update_with_venue_stats():
    state = {
        "seen_paper_ids": [],
        "crawled_venues": [],
        "crawl_history": [],
    }
    config = {"topic": "test", "date_range": {"start": 2024}}
    venue_stats = [
        {"venue": "ISCA", "year": 2024, "papers": 87, "crawled": "2026-04-08"},
        {"venue": "MICRO", "year": 2024, "papers": 115, "crawled": "2026-04-08"},
    ]
    state = update_state(state, "full", MOCK_PAPERS, config, "2024", venue_stats)
    assert len(state["seen_paper_ids"]) == 3
    assert len(state["crawled_venues"]) == 2
    assert state["last_full_crawl"] is not None
    assert len(state["crawl_history"]) == 1

    # All paper_ids have doi: prefix
    for pid in state["seen_paper_ids"]:
        assert pid.startswith("doi:"), f"Expected doi: prefix, got {pid}"
    print("PASS: state_update_with_venue_stats")


def test_csv_required_columns():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        write_csv(MOCK_PAPERS, csv_path, {})
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for required in ["paper_id", "arxiv_id", "s2_paper_id", "doi"]:
                assert required in reader.fieldnames, f"Missing column: {required}"
            rows = list(reader)
            for row in rows:
                assert row["paper_id"].startswith("doi:"), f"Expected doi: prefix: {row['paper_id']}"
                assert row["doi"], f"DOI must not be empty for {row['paper_id']}"
    print("PASS: csv_required_columns")


def test_crossref_abstract_cleaning():
    raw = '<jats:p>We propose a novel <jats:italic>CPU architecture</jats:italic> for AI.</jats:p>'
    cleaned = _clean_crossref_abstract(raw)
    assert "jats:" not in cleaned
    assert "CPU architecture" in cleaned
    print("PASS: crossref_abstract_cleaning")


def test_abstract_fallback_marks_unavailable():
    """Papers with no abstract and no DOI/arxiv_id get marked unavailable."""
    papers = [{
        "paper_id": "dblp:conf/test/Author24",
        "arxiv_id": "",
        "s2_paper_id": "",
        "doi": "",
        "abstract": "",
    }]
    cr, arxiv, unavail = enrich_abstracts(papers, crossref_enabled=False, arxiv_enabled=False)
    assert unavail == 1
    assert papers[0]["abstract"] == "[abstract unavailable]"
    print("PASS: abstract_fallback_marks_unavailable")


def test_update_years_computation():
    state = {
        "crawled_venues": [
            {"venue": "ISCA", "year": 2023},
            {"venue": "ISCA", "year": 2024},
        ],
    }
    config = {"update": {"overlap_years": 1}, "date_range": {"start": 2020}}
    start, end = _compute_update_years(state, config)
    assert start == 2024, f"Expected 2024, got {start}"  # max_year(2024) - overlap(1) + 1
    print("PASS: update_years_computation")


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_slugify,
        test_csv_write_preserves_human_columns,
        test_append_only_new,
        test_idempotent_update,
        test_keyword_scoring,
        test_state_update_with_venue_stats,
        test_csv_required_columns,
        test_crossref_abstract_cleaning,
        test_abstract_fallback_marks_unavailable,
        test_update_years_computation,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("All Gate 1 assertions passed!")
    sys.exit(1 if failed else 0)
