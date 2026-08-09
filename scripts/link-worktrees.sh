#!/usr/bin/env bash
# scripts/link-worktrees.sh — backfill root .claude symlinks over every linked
# worktree of a project (plus the main checkout), and make sure the shared
# .git/info/exclude carries the /.claude line.
#
# Run it after creating new worktrees, or after a transitional repo's
# committed .claude has been removed and checkouts updated.  Worktrees where
# .claude is still TRACKED content are skipped and reported.
#
# Usage: scripts/link-worktrees.sh [--dry-run] [--force] <project> [...]
#        scripts/link-worktrees.sh --all [--dry-run] [--force]

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"
DRY_RUN=0; FORCE=0; ALL=0; TARGETS=()

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --force)   FORCE=1 ;;
    --all)     ALL=1 ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)        die "unknown flag: $arg" ;;
    *)         TARGETS+=("$arg") ;;
  esac
done
[ "$ALL" = 1 ] && mapfile -t TARGETS < <(manifest_projects "$MANIFEST")
[ "${#TARGETS[@]}" -gt 0 ] || die "no project given (or use --all); known: $(manifest_projects "$MANIFEST" | tr '\n' ' ')"

for name in "${TARGETS[@]}"; do
  parent="$(expand_tilde "$(manifest_get "$MANIFEST" "projects.$name" parent)")"
  main="$(manifest_get "$MANIFEST" "projects.$name" main main)"
  mode="$(manifest_get "$MANIFEST" "projects.$name" mode symlink)"
  say "link worktrees: $name  ($parent, main checkout: $main)"
  [ -n "$parent" ] || { fail "unknown project: $name"; continue; }
  if [ "$mode" = committed ]; then
    ok "committed-mode project — worktrees carry their own tracked .claude; nothing to do"
    continue
  fi
  if [ ! -d "$parent/$main" ]; then
    fail "main checkout missing: $parent/$main"
    continue
  fi
  link_worktrees_for "$parent" "$parent/$main"
done

summary "link-worktrees" || exit 1
