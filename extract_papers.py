#!/usr/bin/env python3
"""
Phase 0 v3: Extract full body text from PDF papers.
- NO section splitting — keep all body text as-is
- Metadata (title, authors, venue, year, doi, abstract, citations, etc.) from CSV
- Stop at References section, clean noise
"""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

# ── Noise patterns to remove ────────────────────────────────────────────
NOISE_PATTERNS = [
    re.compile(r"^authorized licensed use limited to:.*$", re.I),
    re.compile(r"^downloaded on .+ from .+$", re.I),
    re.compile(r"^\d{4}\s+ieee\s+international\s+symposium.*$", re.I),
    re.compile(r"^\d{4}\s+ieee/acm\s+international\s+symposium.*$", re.I),
    re.compile(r"^\d{4}\s+ieee/acm\s+international\s+conference.*$", re.I),
    re.compile(r"^\d{4}\s+acm\s+international\s+conference.*$", re.I),
    re.compile(r"^979-\d[\d-]*\d/\d{2}/\$[\d.]+.*$", re.I),  # ISBN/DOI line
    re.compile(r"^doi\s+10\.\d{4,}", re.I),
    re.compile(r"^\d+\s*$"),  # standalone page numbers
    re.compile(r"^restrictions apply\.$", re.I),
    re.compile(r"^open access support provided by:?$", re.I),
    re.compile(r"^pdf download$", re.I),
    re.compile(r"^total citations:.*$", re.I),
    re.compile(r"^total downloads:.*$", re.I),
    re.compile(r"^published:.*$", re.I),
    re.compile(r"^citation in bibtex format$", re.I),
    re.compile(r"^conference sponsors:.*$", re.I),
    re.compile(r"^ccs concepts$", re.I),
    re.compile(r"^acm reference format:?$", re.I),
    re.compile(r"^keywords?\s*$", re.I),  # bare "Keywords" line
    re.compile(r"^this work is licensed under.*$", re.I),
    re.compile(r"^\.$"),  # lone dot lines
]

# References section marker
REFERENCES_HEADING = re.compile(
    r"^(\d{0,2}\.?\s*)?(references|bibliography)\s*$", re.I
)


def is_noise(line: str) -> bool:
    """Return True if line is noise and should be removed."""
    stripped = line.strip()
    if not stripped:
        return True  # blank lines handled during merge
    for pat in NOISE_PATTERNS:
        if pat.match(stripped):
            return True
    return False


def normalize(s: str) -> str:
    """Normalize string for fuzzy matching: lowercase, remove non-alnum."""
    return re.sub(r"[^a-z0-9]", "", s.lower())


def load_csv_index(csv_path: Path) -> dict:
    """Load scored CSV and build a normalized-title -> row index."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    index = {}
    for row in rows:
        norm = normalize(row["title"])
        index[norm] = row
    return index


def find_csv_match(pdf_stem: str, csv_index: dict) -> dict | None:
    """Match PDF filename stem to CSV entry by normalized title."""
    norm_stem = normalize(pdf_stem)
    for norm_title, row in csv_index.items():
        if norm_stem in norm_title or norm_title in norm_stem:
            return row
    return None


def extract_body_text(pdf_path: str) -> str:
    """Extract full body text from PDF, stopping at References, cleaning noise."""
    # Try PyMuPDF first, fallback to pdfplumber
    text = ""
    try:
        doc = fitz.open(pdf_path)
        for page in doc:
            text += page.get_text("text") + "\n"
        doc.close()
    except Exception:
        pass

    if len(text.strip()) < 200:
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    t = page.extract_text()
                    if t:
                        text += t + "\n"
        except Exception:
            pass

    if len(text.strip()) < 200:
        return ""

    lines = text.split("\n")

    # Find where References starts
    ref_start = len(lines)
    for i, line in enumerate(lines):
        if REFERENCES_HEADING.match(line.strip()):
            ref_start = i
            break

    # Collect body lines (everything before References), skip noise
    body_lines = []
    for i in range(ref_start):
        stripped = lines[i].strip()
        if not stripped:
            continue
        if is_noise(lines[i]):
            continue
        body_lines.append(stripped)

    # Merge into paragraphs: group consecutive non-blank lines,
    # separate groups with blank line
    paragraphs = []
    current = []
    for line in body_lines:
        current.append(line)

    # Simply join all lines with spaces within each logical block
    # Re-paragraph: treat double newlines from original as paragraph breaks
    # For simplicity, just join everything with newlines
    return "\n".join(body_lines)


def process_paper(pdf_path: Path, csv_index: dict) -> dict:
    """Process a single PDF: extract body text + metadata from CSV."""
    csv_row = find_csv_match(pdf_path.stem, csv_index)

    body_text = extract_body_text(str(pdf_path))

    result = {
        "file": pdf_path.name,
        # Metadata from CSV
        "title": csv_row.get("title", "") if csv_row else "",
        "authors": csv_row.get("authors", "") if csv_row else "",
        "year": int(csv_row.get("year", 0)) if csv_row and csv_row.get("year") else 0,
        "venue": csv_row.get("venue", "") if csv_row else "",
        "doi": csv_row.get("doi", "") if csv_row else "",
        "url": csv_row.get("url", "") if csv_row else "",
        "abstract": csv_row.get("abstract", "") if csv_row else "",
        "citation_count": csv_row.get("citation_count", "") if csv_row else "",
        "relevance_score": csv_row.get("relevance_score", "") if csv_row else "",
        "relevance": csv_row.get("relevance", "") if csv_row else "",
        "matched_keywords": csv_row.get("matched_keywords", "") if csv_row else "",
        # Body text from PDF
        "body_text": body_text,
        "text_length": len(body_text),
        "csv_matched": csv_row is not None,
        "extraction_status": "success" if len(body_text) >= 200 else "failed",
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Extract full body text from PDF papers, metadata from CSV")
    parser.add_argument("pdf_dir", type=Path, help="Directory containing PDF files")
    parser.add_argument("csv", type=Path, help="Scored CSV file with paper metadata")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output directory for corpus JSON files")
    parser.add_argument("-n", "--limit", type=int, default=0, help="Only process first N PDFs (0=all)")
    args = parser.parse_args()

    pdf_dir: Path = args.pdf_dir
    scored_csv: Path = args.csv
    corpus_dir: Path = args.output
    corpus_dir.mkdir(parents=True, exist_ok=True)

    # Load CSV index
    print(f"Loading CSV: {scored_csv}")
    csv_index = load_csv_index(scored_csv)
    print(f"  {len(csv_index)} papers in CSV index")

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if args.limit > 0:
        pdfs = pdfs[:args.limit]
    print(f"Found {len(pdfs)} PDFs in {pdf_dir}")

    if not pdfs:
        print("No PDFs found. Exiting.")
        sys.exit(1)

    index_entries = []
    ok = 0
    fail = 0
    no_csv = 0

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"[{i:3d}/{len(pdfs)}] {pdf_path.name[:60]}...", end=" ", flush=True)

        result = process_paper(pdf_path, csv_index)

        status = result["extraction_status"]
        csv_ok = result["csv_matched"]
        if not csv_ok:
            no_csv += 1
            print(f"NO_CSV  text={result['text_length']}")
        elif status == "success":
            ok += 1
            print(f"OK  text={result['text_length']}")
        else:
            fail += 1
            print(f"FAILED  text={result['text_length']}")

        # Save individual JSON
        safe_name = pdf_path.stem + ".json"
        out_path = corpus_dir / safe_name
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # Index entry (lightweight — no body_text)
        index_entries.append({
            "file": pdf_path.name,
            "json": safe_name,
            "title": result["title"],
            "venue": result["venue"],
            "year": result["year"],
            "doi": result["doi"],
            "citation_count": result["citation_count"],
            "relevance_score": result["relevance_score"],
            "relevance": result["relevance"],
            "text_length": result["text_length"],
            "csv_matched": csv_ok,
            "status": status,
        })

    # Write index
    index = {
        "total": len(pdfs),
        "success": ok,
        "failed": fail,
        "no_csv_match": no_csv,
        "papers": index_entries,
    }
    with open(corpus_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Done: {ok} ok, {fail} failed, {no_csv} no CSV match, total {len(pdfs)}")


if __name__ == "__main__":
    main()
