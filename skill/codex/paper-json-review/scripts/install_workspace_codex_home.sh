#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/opencute/workspace/survey"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_SRC="$ROOT/skill/codex/paper-json-review"
SKILL_DST="$CODEX_HOME/skills/paper-json-review"

mkdir -p "$CODEX_HOME/skills"
ln -sfn "$SKILL_SRC" "$SKILL_DST"

printf 'CODEX_HOME=%s\n' "$CODEX_HOME"
printf 'Installed skill link: %s -> %s\n' "$SKILL_DST" "$SKILL_SRC"
if [ -e "$HOME/.codex/auth.json" ]; then
  printf 'Auth available at: %s\n' "$HOME/.codex/auth.json"
else
  printf 'Auth not found under ~/.codex. Run codex login.\n'
fi
