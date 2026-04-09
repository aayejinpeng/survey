#!/usr/bin/env python3
"""Deterministic preflight checks for paper dossier review."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any


DEFAULT_CORPUS_DIR = pathlib.Path(
    "/root/opencute/slides/2026.04_todo_yjp-ktbg/workspace/corpus"
)

ALLOWED_THEMES = {
    "1. CPU-side AI acceleration / in-core accelerator",
    "2. Matrix extension / AMX / SME",
    "3. Vector extension / RVV / vector AI enhancement",
    "4. RISC-V custom ISA / open ISA AI extension",
    "5. LLM / Transformer / inference acceleration",
    "6. Quantization / mixed precision / FP8 / BF16 / block scale / mx",
    "7. Compiler / tensor IR / operator generation",
    "8. Memory hierarchy / scratchpad / dataflow / systolic",
    "9. HBM / advanced packaging / multi-node system",
}

ALLOWED_WORKSTREAMS = {"1", "2", "3"}

CHINESE_SUMMARY_FIELDS = [
    "research_purpose",
    "research_significance",
    "key_technique",
    "key_results",
    "proposal_evidence.for_state_of_art",
    "proposal_evidence.for_gap",
    "proposal_evidence.for_feasibility",
]

NUMERIC_TEXT_FIELDS = [
    "key_results",
    "proposal_evidence.for_feasibility",
]


@dataclass
class Issue:
    severity: str
    field: str
    category: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "field": self.field,
            "category": self.category,
            "message": self.message,
        }


def normalize_text(value: str) -> str:
    value = (
        value.replace("ﬀ", "ff")
        .replace("ﬁ", "fi")
        .replace("ﬂ", "fl")
        .replace("ﬃ", "ffi")
        .replace("ﬄ", "ffl")
    )
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u00a0", " ")
    value = re.sub(r"(?<=\w)-\s+(?=\w)", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_get(container: Any, dotted_path: str) -> Any:
    current = container
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def status_from_issues(issues: list[Issue]) -> str:
    if any(issue.severity == "critical" for issue in issues):
        return "fail"
    if issues:
        return "mixed"
    return "pass"


def split_sentences(text: str) -> list[str]:
    collapsed = normalize_text(text)
    if not collapsed:
        return []
    return [chunk.strip() for chunk in re.split(r"(?<=[.!?])\s+", collapsed) if chunk.strip()]


def fuzzy_match_quote(quote: str, sentences: list[str]) -> tuple[str | None, float]:
    quote_norm = normalize_text(quote)
    if not quote_norm or not sentences:
        return None, 0.0
    best_sentence = None
    best_ratio = 0.0
    quote_lower = quote_norm.lower()
    for sentence in sentences:
        ratio = SequenceMatcher(None, quote_lower, sentence.lower()).ratio()
        if ratio > best_ratio:
            best_sentence = sentence
            best_ratio = ratio
    return best_sentence, round(best_ratio, 3)


def extract_numeric_tokens(text: str) -> list[str]:
    raw = re.findall(
        r"\d+(?:\.\d+)?(?:\s?(?:x|X|×|%|ms|s|MB|GB|KB|MHz|GHz|cycles?|TOPS|GOPS|TFLOPS|GFLOPS|亿|万))?",
        text,
    )
    tokens: list[str] = []
    seen: set[str] = set()
    for token in raw:
        normalized = token.strip()
        if not normalized:
            continue
        has_decimal = "." in normalized
        has_unit = bool(re.search(r"[A-Za-z%×亿万]", normalized))
        digits_only = re.sub(r"\D", "", normalized)
        if not has_decimal and not has_unit and len(digits_only) <= 1:
            continue
        key = normalized.lower().replace("×", "x").replace(" ", "")
        if key in seen:
            continue
        seen.add(key)
        tokens.append(normalized)
    return tokens


def normalize_numeric_search_space(text: str) -> str:
    return normalize_text(text).lower().replace("×", "x").replace(" ", "")


def compare_metadata(
    analysis: dict[str, Any], paper: dict[str, Any], issues: list[Issue]
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    specs = [
        ("title", "critical"),
        ("authors", "major"),
        ("year", "critical"),
        ("venue", "major"),
        ("doi", "major"),
    ]
    for field, severity in specs:
        analysis_value = analysis.get(field)
        paper_value = paper.get(field)
        if field == "year":
            matched = analysis_value == paper_value
            status = "pass" if matched else "fail"
        elif field == "authors":
            analysis_norm = normalize_text(str(analysis_value or ""))
            paper_norm = normalize_text(str(paper_value or ""))
            matched = analysis_norm == paper_norm
            partial = bool(analysis_norm and paper_norm) and (
                analysis_norm in paper_norm or paper_norm in analysis_norm
            )
            status = "pass" if matched else "partial" if partial else "fail"
        else:
            matched = normalize_text(str(analysis_value or "")) == normalize_text(str(paper_value or ""))
            status = "pass" if matched else "fail"
        checks.append(
            {
                "field": field,
                "status": status,
                "analysis_value": analysis_value,
                "paper_value": paper_value,
            }
        )
        if status == "fail":
            issues.append(
                Issue(
                    severity=severity,
                    field=field,
                    category="metadata",
                    message="Generated metadata does not match the source paper.",
                )
            )
    return checks


def validate_schema(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[Issue]]:
    checks: list[dict[str, Any]] = []
    issues: list[Issue] = []

    required_fields = {
        "title": str,
        "authors": str,
        "year": int,
        "venue": str,
        "doi": str,
        "research_purpose": str,
        "research_significance": str,
        "contributions": list,
        "theme_primary": str,
        "workstream_fit": str,
        "is_close_baseline_to_cute": bool,
        "key_technique": str,
        "key_results": str,
        "gap_identified": list,
        "proposal_evidence": dict,
    }

    for field, expected_type in required_fields.items():
        value = data.get(field)
        ok = isinstance(value, expected_type)
        checks.append(
            {
                "field": field,
                "status": "pass" if ok else "fail",
                "expected_type": expected_type.__name__,
                "actual_type": type(value).__name__ if value is not None else "missing",
            }
        )
        if not ok:
            issues.append(
                Issue(
                    severity="critical",
                    field=field,
                    category="schema",
                    message=f"Expected {expected_type.__name__}, got {type(value).__name__ if value is not None else 'missing'}.",
                )
            )

    theme_secondary = data.get("theme_secondary")
    if theme_secondary is not None and not isinstance(theme_secondary, str):
        checks.append(
            {
                "field": "theme_secondary",
                "status": "fail",
                "expected_type": "str|null",
                "actual_type": type(theme_secondary).__name__,
            }
        )
        issues.append(
            Issue(
                severity="critical",
                field="theme_secondary",
                category="schema",
                message="theme_secondary must be a string or null.",
            )
        )
    else:
        checks.append(
            {
                "field": "theme_secondary",
                "status": "pass",
                "expected_type": "str|null",
                "actual_type": type(theme_secondary).__name__ if theme_secondary is not None else "null",
            }
        )

    contributions = data.get("contributions")
    if isinstance(contributions, list):
        if not 2 <= len(contributions) <= 5:
            issues.append(
                Issue(
                    severity="major",
                    field="contributions",
                    category="schema",
                    message="contributions should contain 2 to 5 items.",
                )
            )
        for index, item in enumerate(contributions):
            field = f"contributions[{index}]"
            if not isinstance(item, dict):
                issues.append(
                    Issue(
                        severity="critical",
                        field=field,
                        category="schema",
                        message="Each contribution item must be an object.",
                    )
                )
                continue
            for nested in ("point", "evidence"):
                if not isinstance(item.get(nested), str):
                    issues.append(
                        Issue(
                            severity="critical",
                            field=f"{field}.{nested}",
                            category="schema",
                            message=f"{nested} must be a string.",
                        )
                    )

    gaps = data.get("gap_identified")
    if isinstance(gaps, list):
        if not 1 <= len(gaps) <= 5:
            issues.append(
                Issue(
                    severity="major",
                    field="gap_identified",
                    category="schema",
                    message="gap_identified should contain 1 to 5 items.",
                )
            )
        for index, item in enumerate(gaps):
            field = f"gap_identified[{index}]"
            if not isinstance(item, dict):
                issues.append(
                    Issue(
                        severity="critical",
                        field=field,
                        category="schema",
                        message="Each gap item must be an object.",
                    )
                )
                continue
            for nested in ("gap", "evidence", "relevance_to_cute"):
                if not isinstance(item.get(nested), str):
                    issues.append(
                        Issue(
                            severity="critical",
                            field=f"{field}.{nested}",
                            category="schema",
                            message=f"{nested} must be a string.",
                        )
                    )

    proposal = data.get("proposal_evidence")
    if isinstance(proposal, dict):
        for nested in ("for_state_of_art", "for_gap", "for_feasibility"):
            if not isinstance(proposal.get(nested), str):
                issues.append(
                    Issue(
                        severity="critical",
                        field=f"proposal_evidence.{nested}",
                        category="schema",
                        message=f"{nested} must be a string.",
                    )
                )

    theme_primary = data.get("theme_primary")
    if isinstance(theme_primary, str) and theme_primary not in ALLOWED_THEMES:
        issues.append(
            Issue(
                severity="major",
                field="theme_primary",
                category="taxonomy",
                message="theme_primary is not one of the allowed theme strings.",
            )
        )

    if isinstance(theme_secondary, str) and theme_secondary not in ALLOWED_THEMES:
        issues.append(
            Issue(
                severity="major",
                field="theme_secondary",
                category="taxonomy",
                message="theme_secondary is not one of the allowed theme strings.",
            )
        )

    workstream_fit = data.get("workstream_fit")
    if isinstance(workstream_fit, str) and workstream_fit not in ALLOWED_WORKSTREAMS:
        issues.append(
            Issue(
                severity="major",
                field="workstream_fit",
                category="taxonomy",
                message="workstream_fit must be one of 1, 2, or 3.",
            )
        )

    for field_path in CHINESE_SUMMARY_FIELDS:
        value = safe_get(data, field_path)
        if isinstance(value, str) and '"' in value:
            issues.append(
                Issue(
                    severity="minor",
                    field=field_path,
                    category="format",
                    message='Chinese summary field contains ASCII double quote (").',
                )
            )

    for index, item in enumerate(data.get("contributions", [])):
        if isinstance(item, dict) and contains_chinese(str(item.get("evidence", ""))):
            issues.append(
                Issue(
                    severity="major",
                    field=f"contributions[{index}].evidence",
                    category="format",
                    message="Evidence quote contains Chinese characters; expected English source quote.",
                )
            )

    for index, item in enumerate(data.get("gap_identified", [])):
        if isinstance(item, dict) and contains_chinese(str(item.get("evidence", ""))):
            issues.append(
                Issue(
                    severity="major",
                    field=f"gap_identified[{index}].evidence",
                    category="format",
                    message="Evidence quote contains Chinese characters; expected English source quote.",
                )
            )

    return checks, issues


def resolve_paper(
    analysis_path: pathlib.Path,
    analysis: dict[str, Any],
    explicit_paper: pathlib.Path | None,
    corpus_dir: pathlib.Path,
) -> tuple[pathlib.Path, dict[str, Any], str]:
    if explicit_paper is not None:
        return explicit_paper, load_json(explicit_paper), "explicit_path"

    title = str(analysis.get("title") or "").strip()
    doi = str(analysis.get("doi") or "").strip()
    title_key = normalize_key(title)
    analysis_stem_key = normalize_key(analysis_path.stem)
    matches: list[tuple[pathlib.Path, dict[str, Any], str]] = []

    for candidate in sorted(corpus_dir.glob("*.json")):
        paper = load_json(candidate)
        if doi and normalize_text(str(paper.get("doi") or "")) == normalize_text(doi):
            matches.append((candidate, paper, "doi"))
            continue
        candidate_title_key = normalize_key(str(paper.get("title") or ""))
        if title_key and candidate_title_key == title_key:
            matches.append((candidate, paper, "title_exact"))
            continue
        if analysis_stem_key and normalize_key(candidate.stem) == analysis_stem_key:
            matches.append((candidate, paper, "filename_exact"))

    if not matches:
        raise FileNotFoundError("Unable to resolve the source paper from DOI or title.")

    unique = {(path, reason) for path, _, reason in matches}
    if len({path for path, _ in unique}) > 1:
        options = ", ".join(str(path) for path, _, _ in matches[:5])
        raise RuntimeError(f"Paper resolution is ambiguous. Candidates: {options}")

    path, paper, reason = matches[0]
    return path, paper, reason


def run_evidence_checks(
    analysis: dict[str, Any], paper_text: str, issues: list[Issue]
) -> list[dict[str, Any]]:
    paper_norm = normalize_text(paper_text).lower()
    sentences = split_sentences(paper_text)
    checks: list[dict[str, Any]] = []

    candidates: list[tuple[str, str]] = []
    for index, item in enumerate(analysis.get("contributions", [])):
        if isinstance(item, dict):
            candidates.append((f"contributions[{index}].evidence", str(item.get("evidence", ""))))
    for index, item in enumerate(analysis.get("gap_identified", [])):
        if isinstance(item, dict):
            candidates.append((f"gap_identified[{index}].evidence", str(item.get("evidence", ""))))

    for field, quote in candidates:
        quote_norm = normalize_text(quote)
        if not quote_norm:
            checks.append({"field": field, "status": "fail", "match_type": "empty"})
            issues.append(
                Issue(
                    severity="critical",
                    field=field,
                    category="evidence",
                    message="Evidence quote is empty.",
                )
            )
            continue
        matched = quote_norm.lower() in paper_norm
        if matched:
            checks.append({"field": field, "status": "pass", "match_type": "exact"})
            continue
        best_sentence, best_ratio = fuzzy_match_quote(quote_norm, sentences)
        if best_ratio >= 0.85:
            checks.append(
                {
                    "field": field,
                    "status": "partial",
                    "match_type": "near_match",
                    "best_match_ratio": best_ratio,
                    "best_match_sentence": best_sentence,
                }
            )
            issues.append(
                Issue(
                    severity="minor",
                    field=field,
                    category="evidence",
                    message="Evidence quote was not found verbatim, but a near match exists in extracted paper text.",
                )
            )
            continue
        checks.append(
            {
                "field": field,
                "status": "fail",
                "match_type": "not_found",
                "best_match_ratio": best_ratio,
                "best_match_sentence": best_sentence,
            }
        )
        severity = "major" if best_ratio >= 0.6 else "critical"
        issues.append(
            Issue(
                severity=severity,
                field=field,
                category="evidence",
                message="Evidence quote was not found verbatim in the source paper.",
            )
        )

    return checks


def run_numeric_checks(
    analysis: dict[str, Any], paper_text: str, issues: list[Issue]
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    search_space = normalize_numeric_search_space(paper_text)

    for field_path in NUMERIC_TEXT_FIELDS:
        value = safe_get(analysis, field_path)
        if not isinstance(value, str):
            continue
        tokens = extract_numeric_tokens(value)
        for token in tokens:
            key = token.lower().replace("×", "x").replace(" ", "")
            matched = key in search_space
            checks.append(
                {
                    "field": field_path,
                    "token": token,
                    "status": "pass" if matched else "fail",
                }
            )
            if not matched:
                issues.append(
                    Issue(
                        severity="minor",
                        field=field_path,
                        category="numeric",
                        message=f"Numeric token '{token}' was not found in the source paper text.",
                    )
                )

    return checks


def summarize_issues(issues: list[Issue]) -> dict[str, Any]:
    counts = {"critical": 0, "major": 0, "minor": 0}
    for issue in issues:
        counts[issue.severity] += 1
    return {
        "issue_count": len(issues),
        "critical_count": counts["critical"],
        "major_count": counts["major"],
        "minor_count": counts["minor"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-json", required=True, type=pathlib.Path)
    parser.add_argument("--paper-json", type=pathlib.Path)
    parser.add_argument("--corpus-dir", type=pathlib.Path, default=DEFAULT_CORPUS_DIR)
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    try:
        analysis = load_json(args.analysis_json)
        if not isinstance(analysis, dict):
            raise TypeError("analysis-json must contain a JSON object.")
        paper_path, paper, resolved_by = resolve_paper(
            args.analysis_json, analysis, args.paper_json, args.corpus_dir
        )
        if not isinstance(paper, dict):
            raise TypeError("paper-json must contain a JSON object.")
    except Exception as exc:  # pragma: no cover - CLI error path
        print(
            json.dumps(
                {
                    "error": str(exc),
                    "analysis_json_path": str(args.analysis_json),
                    "paper_json_path": str(args.paper_json) if args.paper_json else None,
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    issues: list[Issue] = []
    shape_checks, shape_issues = validate_schema(analysis)
    issues.extend(shape_issues)
    metadata_checks = compare_metadata(analysis, paper, issues)
    paper_text = "\n".join([str(paper.get("abstract") or ""), str(paper.get("body_text") or "")])
    evidence_checks = run_evidence_checks(analysis, paper_text, issues)
    numeric_checks = run_numeric_checks(analysis, paper_text, issues)

    matched_quotes = sum(1 for item in evidence_checks if item.get("status") == "pass")
    total_quotes = len(evidence_checks)
    matched_numbers = sum(1 for item in numeric_checks if item.get("status") == "pass")
    total_numbers = len(numeric_checks)

    report = {
        "analysis_json_path": str(args.analysis_json.resolve()),
        "paper_json_path": str(paper_path.resolve()),
        "resolved_paper_by": resolved_by,
        "analysis_title": analysis.get("title"),
        "paper_title": paper.get("title"),
        "statuses": {
            "schema": status_from_issues([i for i in issues if i.category == "schema"]),
            "metadata": status_from_issues([i for i in issues if i.category == "metadata"]),
            "taxonomy": status_from_issues([i for i in issues if i.category == "taxonomy"]),
            "evidence": status_from_issues([i for i in issues if i.category == "evidence"]),
            "numeric": status_from_issues([i for i in issues if i.category == "numeric"]),
            "format": status_from_issues([i for i in issues if i.category == "format"]),
        },
        "summary": {
            **summarize_issues(issues),
            "matched_evidence_quotes": matched_quotes,
            "total_evidence_quotes": total_quotes,
            "matched_numeric_claims": matched_numbers,
            "total_numeric_claims": total_numbers,
        },
        "metadata_checks": metadata_checks,
        "shape_checks": shape_checks,
        "evidence_checks": evidence_checks,
        "numeric_claim_checks": numeric_checks,
        "issues": [issue.to_dict() for issue in issues],
    }

    serialized = json.dumps(report, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + ("\n" if args.pretty else ""), encoding="utf-8")
    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
