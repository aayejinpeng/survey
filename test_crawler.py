#!/usr/bin/env python3
"""Unit tests for survey_crawler.py — no API calls, pure logic validation."""

import csv
import json
import os
import sys
import tempfile
from pathlib import Path

# Add current dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from survey_crawler import (
    CSV_COLUMNS,
    HUMAN_COLUMNS,
    _slugify,
    dedup_papers,
    load_state,
    read_existing_csv,
    save_state,
    score_by_keywords,
    update_state,
    write_csv,
    append_csv,
)

# ---------------------------------------------------------------------------
# Fixtures: mock paper data
# ---------------------------------------------------------------------------

MOCK_ARXIV_PAPERS = [
    {
        "paper_id": "arxiv:2301.07041",
        "arxiv_id": "2301.07041",
        "s2_paper_id": "",
        "title": "CPU Matrix Extension for AI Inference",
        "authors": "Alice Smith; Bob Jones",
        "year": "2023",
        "venue": "arXiv",
        "abstract": "We propose a CPU matrix extension for efficient AI inference.",
        "source": "arxiv",
        "categories": "cs.AR; cs.PF",
        "citation_count": 0,
        "url": "https://arxiv.org/abs/2301.07041",
        "doi": "",
        "published_date": "2023-01-17",
        "crawled_date": "2026-04-07",
        "keep": "",
        "notes": "",
    },
    {
        "paper_id": "arxiv:2405.12345",
        "arxiv_id": "2405.12345",
        "s2_paper_id": "",
        "title": "RISC-V Tensor Unit Design",
        "authors": "Carol Lee",
        "year": "2024",
        "venue": "arXiv",
        "abstract": "A RISC-V tensor unit for on-device AI acceleration.",
        "source": "arxiv",
        "categories": "cs.AR",
        "citation_count": 0,
        "url": "https://arxiv.org/abs/2405.12345",
        "doi": "",
        "published_date": "2024-05-20",
        "crawled_date": "2026-04-07",
        "keep": "",
        "notes": "",
    },
]

MOCK_S2_PAPERS = [
    {
        # Overlaps with arxiv:2301.07041 via arxiv_id
        "paper_id": "arxiv:2301.07041",
        "arxiv_id": "2301.07041",
        "s2_paper_id": "abc123def456",
        "title": "CPU Matrix Extension for AI Inference",
        "authors": "Alice Smith; Bob Jones",
        "year": "2023",
        "venue": "ISCA 2023",
        "abstract": "We propose a CPU matrix extension for efficient AI inference.",
        "source": "semantic_scholar",
        "categories": "Computer Science",
        "citation_count": 42,
        "url": "https://www.semanticscholar.org/paper/abc123def456",
        "doi": "10.1109/ISCA.2023.1234",
        "published_date": "2023-06-15",
        "crawled_date": "2026-04-07",
        "keep": "",
        "notes": "",
    },
    {
        # Pure S2 paper (no arXiv)
        "paper_id": "s2:xyz789ghi012",
        "arxiv_id": "",
        "s2_paper_id": "xyz789ghi012",
        "title": "Intel AMX Performance Characterization",
        "authors": "David Wang; Eve Chen",
        "year": "2024",
        "venue": "MICRO 2024",
        "abstract": "We characterize Intel AMX performance on AI workloads.",
        "source": "semantic_scholar",
        "categories": "Computer Science; Engineering",
        "citation_count": 15,
        "url": "https://www.semanticscholar.org/paper/xyz789ghi012",
        "doi": "10.1145/MICRO.2024.5678",
        "published_date": "2024-10-20",
        "crawled_date": "2026-04-07",
        "keep": "",
        "notes": "",
    },
]


def test_slugify():
    assert _slugify("CPU AI acceleration") == "cpu-ai-acceleration"
    assert _slugify("RISC-V tensor unit!") == "risc-v-tensor-unit"
    assert _slugify("  spaces  ") == "spaces"
    print("PASS: _slugify")


def test_dedup_merges_arxiv_s2_overlap():
    """arXiv paper 2301.07041 also appears in S2 with richer metadata.
    After dedup, should be ONE entry with merged metadata."""
    merged = dedup_papers(MOCK_ARXIV_PAPERS, MOCK_S2_PAPERS)

    # Should have 3 unique papers (2301.07041 merged, 2405.12345 arXiv-only, xyz789ghi012 S2-only)
    ids = {p["paper_id"] for p in merged}
    assert len(merged) == 3, f"Expected 3, got {len(merged)}: {ids}"

    # The merged arXiv paper should have S2 metadata
    merged_arxiv = next(p for p in merged if p["arxiv_id"] == "2301.07041")
    assert merged_arxiv["s2_paper_id"] == "abc123def456", \
        f"Expected s2_paper_id='abc123def456', got '{merged_arxiv['s2_paper_id']}'"
    assert merged_arxiv["citation_count"] == 42, \
        f"Expected citation_count=42, got {merged_arxiv['citation_count']}"
    assert merged_arxiv["doi"] == "10.1109/ISCA.2023.1234", \
        f"Expected DOI from S2, got '{merged_arxiv['doi']}'"

    # S2-only paper should have s2: prefix
    s2_only = next(p for p in merged if p["s2_paper_id"] == "xyz789ghi012")
    assert s2_only["paper_id"] == "s2:xyz789ghi012"

    print("PASS: dedup_merges_arxiv_s2_overlap")


def test_csv_write_and_preserve_human_columns():
    """Write CSV, then write again with updated machine data.
    Human columns (keep/notes) must survive the re-write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")

        # First write
        write_csv(MOCK_ARXIV_PAPERS, csv_path, {})

        # Simulate user editing: set keep=yes on first paper
        rows, human = read_existing_csv(csv_path)
        assert len(rows) == 2
        human["arxiv:2301.07041"] = {"keep": "yes", "notes": "important paper"}

        # Re-write (simulating full re-crawl)
        updated_papers = list(MOCK_ARXIV_PAPERS)
        updated_papers[0]["abstract"] = "Updated abstract"  # machine column changed
        write_csv(updated_papers, csv_path, human)

        # Verify human columns preserved
        rows2, human2 = read_existing_csv(csv_path)
        first_row = next(r for r in rows2 if r["paper_id"] == "arxiv:2301.07041")
        assert first_row["keep"] == "yes", f"Expected keep='yes', got '{first_row['keep']}'"
        assert first_row["notes"] == "important paper", \
            f"Expected notes='important paper', got '{first_row['notes']}'"
        assert first_row["abstract"] == "Updated abstract", "Machine column should be updated"

        print("PASS: csv_write_and_preserve_human_columns")


def test_update_mode_appends_only_new():
    """Update mode should only append papers not already in seen_paper_ids."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")

        # Initial full write
        write_csv(MOCK_ARXIV_PAPERS, csv_path, {})

        # Update: try to add same + new papers
        new_papers = list(MOCK_S2_PAPERS)  # 2301.07041 (duplicate) + xyz789ghi012 (new)
        seen_ids = {"arxiv:2301.07041", "arxiv:2405.12345"}  # already in CSV
        count = append_csv(new_papers, csv_path, seen_ids)

        assert count == 1, f"Expected 1 new paper appended, got {count}"

        rows, _ = read_existing_csv(csv_path)
        assert len(rows) == 3, f"Expected 3 total rows, got {len(rows)}"

        ids = {r["paper_id"] for r in rows}
        assert "s2:xyz789ghi012" in ids, "New S2 paper should be in CSV"
        assert rows[0]["paper_id"] == "arxiv:2301.07041", "Original row preserved"

        print("PASS: update_mode_appends_only_new")


def test_idempotent_update():
    """Running update twice with same data should add 0 papers the second time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        write_csv(MOCK_ARXIV_PAPERS, csv_path, {})

        seen_ids = {"arxiv:2301.07041", "arxiv:2405.12345"}
        new_papers = [MOCK_S2_PAPERS[1]]  # s2:xyz789ghi012

        # First update
        count1 = append_csv(new_papers, csv_path, seen_ids)
        assert count1 == 1

        # Update seen_ids
        seen_ids.add("s2:xyz789ghi012")

        # Second update with same data
        count2 = append_csv(new_papers, csv_path, seen_ids)
        assert count2 == 0, f"Expected 0 on second run, got {count2}"

        rows, _ = read_existing_csv(csv_path)
        assert len(rows) == 3, "Should still be 3 rows"

        print("PASS: idempotent_update")


def test_keyword_scoring():
    """Papers with more keyword matches should rank higher."""
    papers = list(MOCK_ARXIV_PAPERS) + list(MOCK_S2_PAPERS)
    keywords = ["AMX", "Intel", "tensor"]
    scored = score_by_keywords(papers, keywords)

    # "Intel AMX Performance Characterization" should rank first
    assert scored[0]["title"] == "Intel AMX Performance Characterization", \
        f"Expected Intel AMX paper first, got '{scored[0]['title']}'"

    print("PASS: keyword_scoring")


def test_state_update():
    """State tracking should accumulate seen IDs and history."""
    state = load_state("/nonexistent/state.json")
    config = {"topic": "test topic", "date_range": {"start": "2023-01-01"}}

    # Simulate full crawl
    state = update_state(state, "full", MOCK_ARXIV_PAPERS, config, "2023-01-01")
    assert "arxiv:2301.07041" in state["seen_paper_ids"]
    assert state["last_full_crawl"] is not None
    assert len(state["crawl_history"]) == 1

    # Simulate update crawl
    state = update_state(state, "update", MOCK_S2_PAPERS, config, "2026-04-01")
    assert "s2:xyz789ghi012" in state["seen_paper_ids"]
    assert len(state["seen_paper_ids"]) == 3  # 2 arXiv + 1 new S2 (arxiv:2301.07041 overlaps)
    assert len(state["crawl_history"]) == 2

    # Gate 4 check: seen_paper_ids are canonical
    for pid in state["seen_paper_ids"]:
        assert pid.startswith("arxiv:") or pid.startswith("s2:"), f"Bad paper_id format: {pid}"

    print("PASS: state_update")


def test_csv_has_required_columns():
    """CSV output must contain paper_id, arxiv_id, s2_paper_id columns."""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "test.csv")
        merged = dedup_papers(MOCK_ARXIV_PAPERS, MOCK_S2_PAPERS)
        write_csv(merged, csv_path, {})

        with open(csv_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = reader.fieldnames
            for required in ["paper_id", "arxiv_id", "s2_paper_id"]:
                assert required in cols, f"Missing required column: {required}"

            rows = list(reader)
            for row in rows:
                assert row["paper_id"], "paper_id must not be empty"
                assert row["arxiv_id"] or row["s2_paper_id"], \
                    f"At least one of arxiv_id/s2_paper_id must be set for {row['paper_id']}"

        print("PASS: csv_has_required_columns")


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_slugify,
        test_dedup_merges_arxiv_s2_overlap,
        test_csv_write_and_preserve_human_columns,
        test_update_mode_appends_only_new,
        test_idempotent_update,
        test_keyword_scoring,
        test_state_update,
        test_csv_has_required_columns,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"ERROR: {test.__name__}: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed, {passed + failed} total")
    if failed == 0:
        print("All Gate 1 assertions passed!")
    sys.exit(1 if failed else 0)
