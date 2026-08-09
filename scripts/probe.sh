#!/usr/bin/env bash
# scripts/probe.sh — the LIVE verification matrix.  Opt-in: spawns real
# `claude -p` sessions (2 per location, model haiku by default), so it costs
# tokens.  Static checks are `make check`; this proves discovery BEHAVIOR.
#
# For $HOME and each symlink-mode project's main checkout, asserts:
#   • every managed skill for that scope is visible;
#   • no skill unique to a FOREIGN project leaks in;
#   • the scope's CLAUDE.md PROBE-MARKER is quoted (only once the live file
#     actually carries the marker, i.e. after that migration stage);
#   • no foreign project's PROBE-MARKER is quoted.
#
# Built-in/plugin skills are ignored: assertions are presence/absence of
# MANAGED names, never exact-set equality (sessions always see harness
# skills this repo does not manage).
#
# Usage: scripts/probe.sh [global|<project> ...]      (no names = everything)
#   CLAUDE_PROBE_MODEL=haiku overrides the model.

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"
MODEL="${CLAUDE_PROBE_MODEL:-haiku}"
TARGETS=("$@")

want() {
  [ "${#TARGETS[@]}" -eq 0 ] && return 0
  local t; for t in "${TARGETS[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

skills_in() { # skills_in <dir> — subdir names, one per line
  local d
  for d in "$1"/*/; do [ -d "$d" ] && basename "$d"; done 2>/dev/null || true
}

# ------------------------------------------------- expectations from repo --
global_skills="$(skills_in "$ROOT/global/skills")"
declare -A PROJ_SKILLS PROJ_PARENT PROJ_MODE
all_project_skills=""
for p in $(manifest_projects "$MANIFEST"); do
  PROJ_PARENT[$p]="$(expand_tilde "$(manifest_get "$MANIFEST" "projects.$p" parent)")"
  PROJ_MODE[$p]="$(manifest_get "$MANIFEST" "projects.$p" mode symlink)"
  [ "${PROJ_MODE[$p]}" = symlink ] || continue
  PROJ_SKILLS[$p]="$(skills_in "$ROOT/projects/$p/claude/skills")"
  all_project_skills="$(printf '%s\n%s' "$all_project_skills" "${PROJ_SKILLS[$p]}")"
done
all_project_skills="$(printf '%s' "$all_project_skills" | sort -u | grep -v '^$' || true)"

foreign_to() { # foreign_to <own-names> — project skills not in <own> nor global
  comm -23 <(printf '%s\n' "$all_project_skills") \
           <(printf '%s\n%s\n' "$1" "$global_skills" | sort -u | grep -v '^$' || true)
}

probe_session() { ( cd "$1" && claude --model "$MODEL" -p "$2" < /dev/null 2>&1 ); }

calls=0
check_location() { # <label> <cwd> <expect-skills> <absent-skills> <own-marker|-> <live-claude-md|-> <foreign-markers>
  local label="$1" cwd="$2" expect="$3" absent="$4" marker="$5" live_md="$6" foreign="$7"
  local out s m
  [ -d "$cwd" ] || { fail "[$label] cwd missing: $cwd"; return; }

  say "[$label] skills probe from $cwd"
  out="$(probe_session "$cwd" 'Output only the names of your available skills, one per line. No other text.')"
  calls=$((calls+1))
  while IFS= read -r s; do
    [ -n "$s" ] || continue
    if printf '%s\n' "$out" | grep -qF "$s"; then ok "[$label] skill visible: $s"
    else fail "[$label] managed skill MISSING: $s"; fi
  done <<< "$expect"
  while IFS= read -r s; do
    [ -n "$s" ] || continue
    if printf '%s\n' "$out" | grep -qF "$s"; then fail "[$label] foreign skill LEAKED: $s"
    else ok "[$label] foreign skill absent: $s"; fi
  done <<< "$absent"

  say "[$label] CLAUDE.md marker probe"
  out="$(probe_session "$cwd" 'Output every line of your context that contains the string PROBE-MARKER, verbatim. If there are none, output exactly NONE.')"
  calls=$((calls+1))
  if [ "$marker" != "-" ]; then
    if [ -n "$live_md" ] && [ "$live_md" != "-" ] && [ -e "$live_md" ] && grep -qF "$marker" "$live_md"; then
      if printf '%s\n' "$out" | grep -qF "$marker"; then ok "[$label] own CLAUDE.md marker quoted"
      else fail "[$label] own CLAUDE.md marker NOT quoted ($marker)"; fi
    else
      warn "[$label] marker not deployed in live CLAUDE.md yet — skipped (pre-migration)"
    fi
  fi
  while IFS= read -r m; do
    [ -n "$m" ] || continue
    if printf '%s\n' "$out" | grep -qF "$m"; then fail "[$label] FOREIGN marker leaked: $m"
    else ok "[$label] foreign marker absent: $m"; fi
  done <<< "$foreign"
}

marker_of() { printf 'PROBE-MARKER: claude-tooling/%s' "$1"; }

foreign_markers_for() { # all markers except own; global never foreign
  local own="$1" p out=""
  for p in "${!PROJ_SKILLS[@]}"; do
    [ "$p" = "$own" ] && continue
    out="$(printf '%s\n%s' "$out" "$(marker_of "$p")")"
  done
  printf '%s' "$out" | grep -v '^$' || true
}

say "probe model: $MODEL   (each location = 2 claude -p calls)"

if want global; then
  check_location global "$HOME" \
    "$global_skills" \
    "$(foreign_to '')" \
    "$(marker_of global)" "$HOME/.claude/CLAUDE.md" \
    "$(foreign_markers_for '')"
fi

for p in $(manifest_projects "$MANIFEST"); do
  want "$p" || continue
  [ "${PROJ_MODE[$p]}" = symlink ] || continue
  parent="${PROJ_PARENT[$p]}"
  main="$(manifest_get "$MANIFEST" "projects.$p" main main)"
  check_location "$p" "$parent/$main" \
    "$(printf '%s\n%s' "${PROJ_SKILLS[$p]}" "$global_skills" | grep -v '^$' || true)" \
    "$(foreign_to "${PROJ_SKILLS[$p]}")" \
    "$(marker_of "$p")" "$parent/CLAUDE.md" \
    "$(foreign_markers_for "$p")"
done

say "total claude calls: $calls (model: $MODEL)"
summary "probe" || exit 1
