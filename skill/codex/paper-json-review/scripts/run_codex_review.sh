#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: $0 <analysis-json> [paper-json]" >&2
  exit 2
fi

ROOT="/root/opencute/workspace/survey"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_ROOT="$ROOT/skill/codex/paper-json-review"
ANALYSIS_JSON="$1"
PAPER_JSON="${2:-}"
STEM="$(basename "$ANALYSIS_JSON" .json)"
OUT_DIR="/root/opencute/slides/2026.04_todo_yjp-ktbg/workspace/llm_get_point/gpt5.4"
OUT_REVIEW="$OUT_DIR/$STEM.review.json"
OUT_REVISED="$OUT_DIR/$STEM.revised.json"
BUNDLE_FILE="/tmp/$STEM.review_bundle.json"
SCHEMA_FILE="$SKILL_ROOT/references/review-output.schema.json"

bash "$SKILL_ROOT/scripts/install_workspace_codex_home.sh" >/dev/null
mkdir -p "$OUT_DIR"

PROMPT="Use the paper-json-review skill to review $ANALYSIS_JSON"
if [ -n "$PAPER_JSON" ]; then
  PROMPT="$PROMPT against $PAPER_JSON"
else
  PROMPT="$PROMPT against its source paper in the corpus"
fi
PROMPT="$PROMPT. Output only one JSON object with two top-level keys: review and revised_analysis. The review must contain the structured review JSON. The revised_analysis must be the corrected dossier JSON after applying the review findings."

CODEX_HOME="$CODEX_HOME" codex exec \
  --ephemeral \
  -m gpt-5.4 \
  -c 'model_reasoning_effort="low"' \
  --full-auto \
  -C "$ROOT" \
  --output-schema "$SCHEMA_FILE" \
  -o "$BUNDLE_FILE" \
  "$PROMPT"

python - "$BUNDLE_FILE" "$OUT_REVIEW" "$OUT_REVISED" <<'PY'
import json
import pathlib
import sys

bundle_path = pathlib.Path(sys.argv[1])
review_path = pathlib.Path(sys.argv[2])
revised_path = pathlib.Path(sys.argv[3])

bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
review_path.write_text(
    json.dumps(bundle["review"], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
revised_path.write_text(
    json.dumps(bundle["revised_analysis"], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

rm -f "$BUNDLE_FILE"

printf '%s\n%s\n' "$OUT_REVIEW" "$OUT_REVISED"
