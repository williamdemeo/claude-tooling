#!/usr/bin/env bash
# scripts/list.sh — inventory of managed config by tier: every skill with the
# first line of its description, plus each managed CLAUDE.md.
#
# Usage: scripts/list.sh

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"

desc_of() { # first ~100 chars of the SKILL.md description
  awk '/^description:/{ sub(/^description:[ \t]*/,""); print substr($0,1,100); exit }' "$1"
}

tier() { # tier <label> <claude-md> <skills-dir>
  local label="$1" md="$2" dir="$3" skill n
  say "$label"
  if [ -f "$md" ]; then
    ok "CLAUDE.md ($(wc -l < "$md") lines)"
  else
    warn "no CLAUDE.md"
  fi
  n=0
  if [ -d "$dir" ]; then
    for skill in "$dir"/*/; do
      [ -d "$skill" ] || continue
      n=$((n+1))
      printf '      %-34s %s\n' "$(basename "$skill")" "$(desc_of "$skill/SKILL.md")…"
    done
  fi
  [ "$n" -eq 0 ] && printf '      (no skills yet)\n'
}

tier "global → ~/.claude" "$ROOT/global/CLAUDE.md" "$ROOT/global/skills"

for p in $(manifest_projects "$MANIFEST"); do
  mode="$(manifest_get "$MANIFEST" "projects.$p" mode symlink)"
  parent="$(manifest_get "$MANIFEST" "projects.$p" parent)"
  if [ "$mode" = committed ]; then
    say "$p → $parent  (committed mode: config lives in that repo; not managed here)"
    continue
  fi
  tier "$p → $parent" "$ROOT/projects/$p/CLAUDE.md" "$ROOT/projects/$p/claude/skills"
done
