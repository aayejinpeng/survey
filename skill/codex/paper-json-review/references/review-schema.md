# Review Output Contract

Output only one JSON object with this shape:

```json
{
  "review": {
    "review_target": {
      "analysis_json_path": "/abs/path/to/generated.json",
      "paper_json_path": "/abs/path/to/paper.json",
      "analysis_title": "string",
      "paper_title": "string",
      "resolved_paper_by": "explicit_path | doi | title_exact | filename_exact | manual"
    },
    "overall_verdict": "pass | minor_revision | major_revision | reject",
    "ready_for_proposal_use": false,
    "confidence": "high | medium | low",
    "summary": "中文总结，2-4句话",
    "checks": {
      "schema": "pass | mixed | fail",
      "metadata": "pass | mixed | fail",
      "evidence_quotes": "pass | mixed | fail",
      "semantic_grounding": "pass | mixed | fail",
      "taxonomy_mapping": "pass | mixed | fail",
      "numeric_claims": "pass | mixed | fail"
    },
    "field_reviews": [
      {
        "field": "research_purpose",
        "status": "supported | partially_supported | unsupported | incorrect | format_error",
        "severity": "critical | major | minor",
        "reason": "中文说明",
        "paper_evidence": "英文原文；若缺失则写 信息不足，无法从文本中提取",
        "suggested_fix": "中文修订建议；若无需修改则写 保持不变"
      }
    ],
    "issues": [
      {
        "severity": "critical | major | minor",
        "field": "contributions[1].evidence",
        "problem": "中文说明具体问题",
        "paper_evidence": "英文原文；若缺失则写 信息不足，无法从文本中提取",
        "recommended_action": "中文建议动作"
      }
    ],
    "stats": {
      "required_field_count": 17,
      "missing_required_fields": [],
      "matched_evidence_quotes": 0,
      "total_evidence_quotes": 0,
      "matched_numeric_claims": 0,
      "total_numeric_claims": 0
    }
  },
  "revised_analysis": {
    "title": "string",
    "authors": "string",
    "year": 2025,
    "venue": "string",
    "doi": "string",
    "research_purpose": "string",
    "research_significance": "string",
    "contributions": [
      {
        "point": "string",
        "evidence": "string"
      }
    ],
    "theme_primary": "string",
    "theme_secondary": "string or null",
    "workstream_fit": "1 | 2 | 3",
    "is_close_baseline_to_cute": false,
    "key_technique": "string",
    "key_results": "string",
    "gap_identified": [
      {
        "gap": "string",
        "evidence": "string",
        "relevance_to_cute": "string"
      }
    ],
    "proposal_evidence": {
      "for_state_of_art": "string",
      "for_gap": "string",
      "for_feasibility": "string"
    }
  }
}
```

`review` follows the review object contract below.
`revised_analysis` must be the corrected dossier after applying the review findings and must follow the analysis contract.

## Required review coverage

Inside `review.field_reviews`, cover these dossier sections:

- `research_purpose`
- `research_significance`
- `contributions`
- `theme_primary`
- `theme_secondary`
- `workstream_fit`
- `is_close_baseline_to_cute`
- `key_technique`
- `key_results`
- `gap_identified`
- `proposal_evidence.for_state_of_art`
- `proposal_evidence.for_gap`
- `proposal_evidence.for_feasibility`

Use `review.issues` for pinpointed problems such as a fabricated quote, incorrect number, or unsupported conclusion.

## Revised analysis requirements

- `revised_analysis` must preserve the original dossier schema.
- Fix every `critical` issue in `review`.
- Prefer conservative wording over speculative wording.
- Keep `evidence` fields as direct English quotes from the paper.
- If a detail cannot be confidently corrected from the paper text, replace the risky wording with a safer formulation or `信息不足，无法从文本中提取`.

## Verdict guidance

- `pass`: no meaningful factual issue; minor wording cleanup at most.
- `minor_revision`: mostly faithful, but some fields need small corrections.
- `major_revision`: multiple important fields are overstated, weakly grounded, or classification is wrong.
- `reject`: the dossier is unreliable because core evidence, quotes, or claims fail grounding.

## Severity guidance

- `critical`: fabricated quote, reversed conclusion, wrong core result, or fundamentally wrong paper match
- `major`: key field overstated, unsupported technical detail, wrong theme/workstream/baseline classification
- `minor`: wording too strong, incomplete nuance, formatting issue, or weak but salvageable paraphrase
