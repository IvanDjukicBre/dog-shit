#!/usr/bin/env bash
# Builds dist/dog-shit.skill -- a zip archive of the skill directory.
# The Agent Skills spec does not define a package format; .skill is the
# de-facto convention (a zip whose root entry is the skill directory).
set -euo pipefail
cd "$(dirname "$0")"
OUT="dist/dog-shit.skill"
mkdir -p dist
rm -f "$OUT"

if command -v skills-ref >/dev/null 2>&1; then
  skills-ref validate ./dog-shit
elif [ -x "$HOME/.local/bin/skills-ref" ]; then
  "$HOME/.local/bin/skills-ref" validate ./dog-shit
else
  echo "package: WARNING -- skills-ref not found, packaging without validation" >&2
fi

zip -q -r "$OUT" dog-shit \
  -x '*/__pycache__/*' '*.pyc' '*/.dog-shit/*' '*/.DS_Store'
echo "built $OUT ($(du -h "$OUT" | cut -f1))"
unzip -l "$OUT" | tail -n +4 | head -20
