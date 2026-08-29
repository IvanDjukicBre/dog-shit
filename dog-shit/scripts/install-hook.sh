#!/usr/bin/env bash
# Installs the escape-hatch hook into ~/.claude/settings.json.
# Requires jq. Idempotent. Prints the diff it is about to make and asks first.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SETTINGS="${CLAUDE_SETTINGS:-$HOME/.claude/settings.json}"
CMD="python3 $SKILL_DIR/assets/hooks/dogshit_override.py"

command -v jq >/dev/null || { echo "install-hook: jq is required" >&2; exit 1; }
mkdir -p "$(dirname "$SETTINGS")"
[ -f "$SETTINGS" ] || echo '{}' > "$SETTINGS"

if jq -e --arg c "$CMD" '[.hooks.UserPromptSubmit[]?.hooks[]?.command] | index($c)' \
      "$SETTINGS" >/dev/null 2>&1; then
  echo "install-hook: already installed."
  exit 0
fi

TMP="$(mktemp)"
jq --arg c "$CMD" '
  .hooks //= {} |
  .hooks.UserPromptSubmit //= [] |
  .hooks.UserPromptSubmit += [{"hooks":[{"type":"command","command":$c}]}]
' "$SETTINGS" > "$TMP"

echo "About to add this hook to $SETTINGS:"
echo "  $CMD"
printf 'Proceed? [y/N] '
read -r reply
case "$reply" in
  y|Y) cp "$SETTINGS" "$SETTINGS.dogshit-backup" && mv "$TMP" "$SETTINGS"
       echo "install-hook: installed (backup at $SETTINGS.dogshit-backup)" ;;
  *)   rm -f "$TMP"; echo "install-hook: aborted." ;;
esac
