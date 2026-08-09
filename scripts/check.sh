#!/usr/bin/env bash
# scripts/check.sh — static verification, zero tokens.
#
# Three layers:
#   1. manifest sanity      — projects.toml parses; parents/main checkouts exist
#   2. repo hygiene         — lint-skills.py (frontmatter, duplicate names per
#                             visible set, stale paths, session junk, markers);
#                             no settings.local.json tracked in this repo
#   3. install state        — for global + each symlink project, classify every
#                             expected live location:
#                               ✓ linked into this repo
#                               ! pending (real file / not installed yet — the
#                                 expected state before that migration stage)
#                               ✗ broken (dangling or wrong-target symlink,
#                                 or a repo-pointing link that dangles)
#
# Exit 1 on any ✗.  Pending items are warnings so the check is useful (and
# honest) at every stage of the migration.
#
# Usage: scripts/check.sh [global|<project> ...]     (no names = everything)

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"
TARGETS=("$@")

want() {
  [ "${#TARGETS[@]}" -eq 0 ] && return 0
  local t; for t in "${TARGETS[@]}"; do [ "$t" = "$1" ] && return 0; done
  return 1
}

# classify_link <target> <link> <desc> — install-state classification (layer 3)
classify_link() {
  local target="$1" link="$2" desc="$3" cur
  if [ -L "$link" ]; then
    cur="$(readlink "$link")"
    if [ "$cur" = "$target" ]; then
      if [ -e "$link" ]; then ok "$desc → linked"
      else fail "$desc → correct symlink but target missing in repo: $target"; fi
    else
      case "$cur" in
        "$ROOT"/*) fail "$desc → symlink into repo but WRONG target (→ $cur)" ;;
        *)         fail "$desc → symlink to foreign target (→ $cur)" ;;
      esac
    fi
  elif [ -e "$link" ]; then
    warn "$desc → real file/dir (pending migration)"
  else
    warn "$desc → absent (not installed yet)"
  fi
}

# sweep_orphans <dir> <desc> — symlinks under <dir> (depth 1) that point into
# this repo but dangle (e.g. after a skill rename)
sweep_orphans() {
  local dir="$1" desc="$2" entry cur
  [ -d "$dir" ] || return 0
  for entry in "$dir"/* "$dir"/.[!.]*; do
    [ -L "$entry" ] || continue
    cur="$(readlink "$entry")"
    case "$cur" in
      "$ROOT"/*) [ -e "$entry" ] || fail "$desc: orphaned repo link $(basename "$entry") (→ $cur)" ;;
    esac
  done
}

# ---------------------------------------------------------- 1. manifest ----
say "manifest: $MANIFEST"
[ -f "$MANIFEST" ] || die "projects.toml missing"
projects="$(manifest_projects "$MANIFEST")"
[ -n "$projects" ] || die "no projects parsed from manifest"
ok "parsed projects: $(echo "$projects" | tr '\n' ' ')"

for p in $projects; do
  parent="$(expand_tilde "$(manifest_get "$MANIFEST" "projects.$p" parent)")"
  main="$(manifest_get "$MANIFEST" "projects.$p" main main)"
  mode="$(manifest_get "$MANIFEST" "projects.$p" mode symlink)"
  case "$mode" in symlink|committed) ;; *) fail "$p: invalid mode '$mode'";; esac
  [ -d "$parent" ] || fail "$p: parent missing: $parent"
  [ -d "$parent/$main" ] || fail "$p: main checkout missing: $parent/$main"
  if [ "$mode" = symlink ] && [ ! -d "$ROOT/projects/$p" ]; then
    fail "$p: symlink-mode but no projects/$p dir in repo"
  fi
  [ -d "$parent/$main" ] && git -C "$parent/$main" rev-parse --git-dir >/dev/null 2>&1 \
    || warn "$p: $parent/$main is not a git checkout"
done

# ------------------------------------------------------- 2. repo hygiene ---
say "repo hygiene"
if python3 "$ROOT/scripts/lint-skills.py" "$ROOT"; then
  ok "lint-skills passed"
else
  fail "lint-skills reported errors"
fi
if git -C "$ROOT" ls-files | grep -E '(^|/)settings\.local\.json$' >/dev/null; then
  fail "settings.local.json is TRACKED in this repo — it is machine-local; untrack it"
else
  ok "no settings.local.json tracked"
fi

# ------------------------------------------------------ 3. install state ---
if want global; then
  say "install state: global → ~/.claude"
  classify_link "$ROOT/global/CLAUDE.md" "$HOME/.claude/CLAUDE.md" "~/.claude/CLAUDE.md"
  for skill in "$ROOT"/global/skills/*/; do
    [ -d "$skill" ] || continue
    classify_link "${skill%/}" "$HOME/.claude/skills/$(basename "$skill")" "~/.claude/skills/$(basename "$skill")"
  done
  sweep_orphans "$HOME/.claude/skills" "~/.claude/skills"
fi

for p in $projects; do
  want "$p" || continue
  parent="$(expand_tilde "$(manifest_get "$MANIFEST" "projects.$p" parent)")"
  main="$(manifest_get "$MANIFEST" "projects.$p" main main)"
  mode="$(manifest_get "$MANIFEST" "projects.$p" mode symlink)"
  [ "$mode" = symlink ] || continue
  [ -d "$parent" ] || continue
  say "install state: $p → $parent"
  proj_dir="$ROOT/projects/$p"

  classify_link "$proj_dir/CLAUDE.md" "$parent/CLAUDE.md" "$p/CLAUDE.md"

  if [ -L "$parent/.claude" ]; then
    fail "$p/.claude is a symlink — expected a real dir with per-member links"
  elif [ -d "$parent/.claude" ]; then
    for member in "$proj_dir"/claude/*; do
      [ -e "$member" ] || continue
      base="$(basename "$member")"
      if [ "$base" = skills ]; then
        for skill in "$member"/*/; do
          [ -d "$skill" ] || continue
          classify_link "${skill%/}" "$parent/.claude/skills/$(basename "$skill")" "$p/.claude/skills/$(basename "$skill")"
        done
      else
        classify_link "$member" "$parent/.claude/$base" "$p/.claude/$base"
      fi
    done
    sweep_orphans "$parent/.claude" "$p/.claude"
    sweep_orphans "$parent/.claude/skills" "$p/.claude/skills"
  else
    warn "$p/.claude — absent (not installed yet)"
  fi

  if [ -d "$parent/$main" ]; then
    linked=0; tracked=0; missing=0; broken=0; absent=0
    while IFS= read -r wt; do
      [ -n "$wt" ] || continue
      if [ ! -d "$wt" ]; then missing=$((missing+1)); continue; fi
      if [ -n "$(git -C "$wt" ls-files .claude 2>/dev/null)" ]; then tracked=$((tracked+1)); continue; fi
      if [ -L "$wt/.claude" ]; then
        if [ "$(readlink "$wt/.claude")" = "$parent/.claude" ] && [ -e "$wt/.claude" ]; then
          linked=$((linked+1))
        else
          broken=$((broken+1)); fail "$p worktree ${wt#"$parent"/}: bad .claude link (→ $(readlink "$wt/.claude"))"
        fi
      else
        absent=$((absent+1))
      fi
    done < <(git_worktree_paths "$parent/$main")
    ok "$p worktrees: $linked linked"
    [ "$tracked" -gt 0 ] && warn "$p worktrees: $tracked with tracked .claude (transitional — re-link after removal PR)"
    [ "$absent" -gt 0 ] && warn "$p worktrees: $absent without .claude link (run scripts/link-worktrees.sh $p)"
    [ "$missing" -gt 0 ] && warn "$p worktrees: $missing stale entries missing on disk (git worktree prune)"
    common="$(git_common_dir "$parent/$main" 2>/dev/null)" || true
    if [ -n "${common:-}" ] && [ -f "$common/info/exclude" ] && grep -qxF '/.claude' "$common/info/exclude"; then
      ok "$p: /.claude present in shared info/exclude"
    else
      warn "$p: /.claude not in $common/info/exclude (install adds it)"
    fi
  fi
done

summary "check" || exit 1
