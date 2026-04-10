---
name: "paper-json-review"
description: "Use when the user asks to review a paper-analysis JSON generated from `workspace/corpus/` against the source paper, especially Claude/LLM generated dossier JSON for proposal writing. Resolve the source paper, run the bundled preflight checker, verify claims against the actual paper text, and output both a structured review JSON and a corrected revised dossier JSON."
---

# Paper JSON Review

Review whether an LLM-generated paper dossier is faithful to the original paper JSON in `workspace/corpus/`.

This skill is for the second pass: it does not generate the first draft dossier itself. It checks whether an existing dossier JSON is structurally valid, quote-grounded, and semantically supported by the paper text, then produces a corrected revised dossier JSON.

## When to use

- The user asks to review or audit a Claude/LLM generated paper JSON.
- The user wants machine-readable JSON outputs, not prose comments.
- The source paper lives in `slides/2026.04_todo_yjp-ktbg/workspace/corpus/`.
- The dossier follows the proposal-writing schema described in `references/analysis-contract.md`.

## Skill path

```bash
export CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
export PAPER_JSON_REVIEW_CLI="$CODEX_HOME/skills/paper-json-review/scripts/preflight_review.py"
```

For this repo, keep the skill source in:

`/root/opencute/workspace/survey/skill/codex/paper-json-review`

and link it into:

`$CODEX_HOME/skills/paper-json-review`

using `scripts/install_workspace_codex_home.sh` before invoking Codex CLI.

## Inputs

Prefer these inputs:

1. The generated dossier JSON path to review.
2. Optional source paper JSON path.

If the source paper path is missing, infer it from DOI first, then title.

## Workflow

1. Resolve files.
- Read the dossier JSON.
- Resolve the source paper JSON from `workspace/corpus/`.
- If multiple papers are plausible matches, stop and ask the user for the exact paper.

2. Run the deterministic preflight checker first.

```bash
python "$PAPER_JSON_REVIEW_CLI" \
  --analysis-json /abs/path/to/generated.json \
  --paper-json /abs/path/to/paper.json \
  --pretty
```

If the paper path is omitted:

```bash
python "$PAPER_JSON_REVIEW_CLI" \
  --analysis-json /abs/path/to/generated.json \
  --pretty
```

If you want to invoke the whole review through Codex CLI in this repo, prefer:

```bash
/root/opencute/workspace/survey/skill/codex/paper-json-review/scripts/run_codex_review.sh \
  /root/opencute/slides/2026.04_todo_yjp-ktbg/workspace/llm_get_point/glm5.1/A-Heterogeneous-CNN-Compilation-Framework.json
```

3. Use the preflight report as a floor, not the final answer.
- The script checks structure, metadata alignment, allowed enums, quote presence, and numeric string presence.
- You must still read the paper `abstract` and only the relevant `body_text` passages before final judgment.
- Prefer targeted extraction around disputed claims, quoted evidence, and numeric results. Do not reread the full `body_text` unless preflight cannot localize the needed evidence.
- Focus extra attention on `key_technique`, `key_results`, `gap_identified`, and all `proposal_evidence` fields because these often contain paraphrase drift or invented implications.

4. Review the dossier against the paper.
- Confirm metadata matches the corpus paper.
- Confirm each English `evidence` quote is actually present in the paper text.
- Confirm Chinese summaries do not overstate what the paper proves.
- Confirm numbers, speedups, memory figures, cycle counts, and baselines are faithful.
- Confirm theme/workstream/baseline classification follows `references/analysis-contract.md`.
- Flag unsupported proposal-writing extrapolations even if they sound plausible.

5. Produce the corrected dossier after the review.
- Apply the review findings to generate a revised dossier JSON that follows `references/analysis-contract.md`.
- Preserve supported content.
- Fix incorrect quotes, numbers, and overstatements.
- If a claim cannot be supported by the paper, either rewrite it conservatively or replace it with `信息不足，无法从文本中提取`.

6. Output only one bundle JSON.
- Follow `references/review-schema.md`.
- Do not output Markdown.
- Do not wrap the JSON in code fences.
- Start with `{` and end with `}`.
- The final object must contain both top-level keys: `review` and `revised_analysis`.

## Review standards

- Be conservative: unsupported is better than guessed.
- Distinguish `partially_supported` from `incorrect`.
- Quote English paper text in `paper_evidence` when possible.
- If the paper text is insufficient, write `信息不足，无法从文本中提取`.
- Prefer a small number of precise issues over many vague complaints.
- If the dossier is usable with small edits, use `minor_revision`.
- If multiple core fields are unsupported or quotes are fabricated, use `major_revision` or `reject`.
- `revised_analysis` should be immediately usable for downstream web inspection.

## Output and save conventions

- If the user only asks for the review, still produce both the review and the corrected revised dossier JSON.
- If the user asks to save it, prefer:
  `slides/2026.04_todo_yjp-ktbg/workspace/llm_get_point/gpt5.4/<paper-stem>.review.json`
- And also save:
  `slides/2026.04_todo_yjp-ktbg/workspace/llm_get_point/gpt5.4/<paper-stem>.revised.json`

## References

- Target dossier contract: `references/analysis-contract.md`
- Review output contract: `references/review-schema.md`
- JSON Schema for `codex exec --output-schema`: `references/review-output.schema.json`
