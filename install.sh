#!/usr/bin/env bash
set -euo pipefail

FORCE=0
if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$REPO_ROOT/.agents/skills/ai-dg-estimator"
SKILLS_ROOT="$HOME/.agents/skills"
DESTINATION="$SKILLS_ROOT/ai-dg-estimator"

[[ -d "$SOURCE" ]] || { echo "Skill source not found: $SOURCE" >&2; exit 1; }
mkdir -p "$SKILLS_ROOT"

if [[ -e "$DESTINATION" ]]; then
  if [[ "$FORCE" -ne 1 ]]; then
    echo "Skill already installed at $DESTINATION. Re-run with --force to replace it." >&2
    exit 2
  fi
  rm -rf "$DESTINATION"
fi

cp -R "$SOURCE" "$DESTINATION"
echo "Installed AI-dg skill to: $DESTINATION"
echo "Codex and OpenCode can both discover ~/.agents/skills/ai-dg-estimator."
echo "Restart the agent app/CLI if the skill does not appear immediately."
