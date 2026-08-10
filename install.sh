#!/usr/bin/env bash
# install.sh — deploy William's Claude Code config from this repo via symlinks.
#
# Reads projects.toml and, for the global tier plus every mode="symlink"
# project, guarantees the live locations are symlinks into this repo:
#
#   global:  ~/.claude/CLAUDE.md            -> global/CLAUDE.md
#            ~/.claude/skills/<name>        -> global/skills/<name>      (per skill)
#   project: <parent>/CLAUDE.md             -> projects/<p>/CLAUDE.md
#            <parent>/.claude/              real dir (local state stays out of the repo)
#              skills/<name>                -> projects/<p>/claude/skills/<name>  (per skill)
#              <other member, e.g. hooks/>  -> projects/<p>/claude/<member>
#            main checkout + every linked worktree root:
#              .claude                      -> <parent>/.claude
#            plus a /.claude line in the shared .git/info/exclude
#
# Safety: idempotent; never replaces a real (non-symlink) file unless --force
# (which moves the original to ~/.local/state/claude-tooling/backups/<ts>/…);
# always SKIPS checkouts where .claude is tracked content (transitional
# repos, pre-removal-PR); mode="committed" projects are never touched.
#
# Usage: install.sh [--dry-run] [--force] [global|<project> ...]
#   No names = everything.  Exit 1 only on hard errors (warnings = pending
#   migration steps, expected mid-migration).
#
# Output markers:  ✓ done   → planned (dry-run)   ! expected/transitional
#   !! NEEDS ATTENTION (recapped at the end — the only lines you must read)
#   ✗ hard error

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/scripts/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"
DRY_RUN=0; FORCE=0; TARGETS=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    -h|--help) sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)        die "unknown flag: $arg" ;;
    *)         TARGETS+=("$arg") ;;
  esac
done

canonical="$(expand_tilde "$(manifest_get "$MANIFEST" meta canonical_root)")"
if [ -n "$canonical" ] && [ "$ROOT" != "$canonical" ]; then
  warn "running from $ROOT, not the canonical checkout ($canonical) — links will point HERE"
fi
[ "$DRY_RUN" = 1 ] && say "DRY RUN — nothing will be touched"

want() { # want <name> — is this target selected?
  [ "${#TARGETS[@]}" -eq 0 ] && return 0
  local t; for t in "${TARGETS[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

# ------------------------------------------------------------------ global --
install_global() {
  say "global → ~/.claude"
  ensure_link "$ROOT/global/CLAUDE.md" "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md"
  ensure_realdir "$HOME/.claude/skills" "~/.claude/skills"
  local skill name
  for skill in "$ROOT"/global/skills/*/; do
    [ -d "$skill" ] || continue
    name="$(basename "$skill")"
    ensure_link "${skill%/}" "$HOME/.claude/skills/$name" "~/.claude/skills/$name"
  done
}

# ----------------------------------------------------------------- project --
install_project() {
  local name="$1" parent main mode proj_dir member base skill
  parent="$(expand_tilde "$(manifest_get "$MANIFEST" "projects.$name" parent)")"
  main="$(manifest_get "$MANIFEST" "projects.$name" main main)"
  mode="$(manifest_get "$MANIFEST" "projects.$name" mode symlink)"
  proj_dir="$ROOT/projects/$name"

  say "project $name → $parent  (mode: $mode)"

  if [ "$mode" = committed ]; then
    ok "committed-mode project — config lives in its own repo; nothing to do"
    return
  fi
  [ -d "$parent" ]   || { fail "parent dir missing: $parent"; return; }
  [ -d "$proj_dir" ] || { fail "repo dir missing: $proj_dir"; return; }

  ensure_link "$proj_dir/CLAUDE.md" "$parent/CLAUDE.md" "$name/CLAUDE.md"
  ensure_realdir "$parent/.claude" "$name/.claude"

  for member in "$proj_dir"/claude/*; do
    [ -e "$member" ] || continue
    base="$(basename "$member")"
    case "$base" in
      skills)
        ensure_realdir "$parent/.claude/skills" "$name/.claude/skills"
        for skill in "$member"/*/; do
          [ -d "$skill" ] || continue
          ensure_link "${skill%/}" "$parent/.claude/skills/$(basename "$skill")" \
                      "$name/.claude/skills/$(basename "$skill")"
        done ;;
      settings.local.json)
        warn "repo contains a settings.local.json for $name — that file is machine-local; not linking it" ;;
      *)
        ensure_link "$member" "$parent/.claude/$base" "$name/.claude/$base" ;;
    esac
  done

  if [ -d "$parent/$main" ]; then
    link_worktrees_for "$parent" "$parent/$main"
  else
    fail "main checkout missing: $parent/$main"
  fi
}

# --------------------------------------------------------------------- run --
want global && install_global

for p in $(manifest_projects "$MANIFEST"); do
  want "$p" && install_project "$p"
done

summary "install" || exit 1
