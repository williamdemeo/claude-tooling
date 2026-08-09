#!/usr/bin/env bash
# scripts/add-project.sh — scaffold a new symlink-mode project: manifest
# stanza + projects/<name>/{CLAUDE.md,claude/skills/} skeleton.  This is how
# the setup scales to future projects.
#
# Usage: scripts/add-project.sh <org>/<name> [--parent DIR] [--main NAME]
#   <org>/<name>  e.g. williamdemeo/new-thing → parent ~/git/<org>/<name>
#   --parent DIR  override the parent dir (default ~/git/<org>/<name>)
#   --main NAME   main-checkout dir name (default: main)
#
# Then: edit projects/<name>/CLAUDE.md, drop skills into
# projects/<name>/claude/skills/, and run  make install PROJECT=<name>.

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

ROOT="$(repo_root)"
MANIFEST="$ROOT/projects.toml"
SPEC=""; PARENT=""; MAIN="main"

while [ $# -gt 0 ]; do
  case "$1" in
    --parent) PARENT="$2"; shift 2 ;;
    --main)   MAIN="$2"; shift 2 ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)       die "unknown flag: $1" ;;
    *)        SPEC="$1"; shift ;;
  esac
done

[ -n "$SPEC" ] || die "usage: add-project.sh <org>/<name> [--parent DIR] [--main NAME]"
case "$SPEC" in
  */*) org="${SPEC%%/*}"; name="${SPEC#*/}" ;;
  *)   die "expected <org>/<name>, got: $SPEC" ;;
esac
[ -n "$PARENT" ] || PARENT="~/git/$org/$name"

say "scaffolding project '$name'  (parent: $PARENT, main: $MAIN)"

if manifest_projects "$MANIFEST" | grep -qxF "$name"; then
  die "project '$name' already in $MANIFEST"
fi
if [ -e "$ROOT/projects/$name" ]; then
  die "projects/$name already exists in the repo"
fi

parent_abs="$(expand_tilde "$PARENT")"
[ -d "$parent_abs" ]       || warn "parent dir does not exist yet: $parent_abs"
[ -d "$parent_abs/$MAIN" ] || warn "main checkout does not exist yet: $parent_abs/$MAIN"

mkdir -p "$ROOT/projects/$name/claude/skills"
touch "$ROOT/projects/$name/claude/skills/.gitkeep"
ok "created projects/$name/claude/skills/"

cat > "$ROOT/projects/$name/CLAUDE.md" <<EOF
# $name — working conventions

(Write the project conventions here: build/test commands, layout, git
workflow, style. This file loads into every Claude session under
$PARENT/ via ancestor traversal.)

## Claude config for this project

Managed in williamdemeo/claude-tooling (projects/$name/) and symlinked into
place; project skills belong there, not in ~/.claude/skills/.

<!-- PROBE-MARKER: claude-tooling/$name -->
EOF
ok "created projects/$name/CLAUDE.md (stub)"

cat >> "$MANIFEST" <<EOF

[projects."$name"]
parent = "$PARENT"
main   = "$MAIN"
mode   = "symlink"
EOF
ok "appended manifest stanza to projects.toml"

say "next steps"
printf '  1. edit projects/%s/CLAUDE.md\n' "$name"
printf '  2. add skills under projects/%s/claude/skills/<skill>/SKILL.md\n' "$name"
printf '  3. make check\n'
printf '  4. make install PROJECT=%s   (then: make probe PROJECT=%s)\n' "$name" "$name"

summary "add-project" || exit 1
