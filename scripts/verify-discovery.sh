#!/usr/bin/env bash
# scripts/verify-discovery.sh — empirically verify the Claude Code discovery
# rules this repo's design rests on, using throwaway fixtures and real
# `claude -p` sessions (costs a few haiku calls; touches nothing outside the
# scratch dir).
#
# Shape under test — exactly what install.sh deploys:
#
#   store/…/probeproj/claude/skills/<skill>/     (stand-in for this repo)
#   probeproj/                                   (project parent dir)
#     CLAUDE.md            -> store copy         (symlinked parent CLAUDE.md)
#     .claude/             real dir
#       skills/<skill>     -> store copy         (PER-SKILL symlink)
#     main/                git repo;  .claude -> ../.claude
#     worktrees/wt1/       linked worktree;  .claude -> ../../.claude
#
# Asserts, from the worktree AND the main checkout:
#   1. the probe skill is discovered through the per-skill symlink chain;
#   2. the symlinked parent-level CLAUDE.md loads via ancestor traversal.
#
# Usage: scripts/verify-discovery.sh [scratch-dir]
#   CLAUDE_PROBE_MODEL=haiku (default) overrides the probe model.

set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

MODEL="${CLAUDE_PROBE_MODEL:-haiku}"
scratch="${1:-$(mktemp -d "${TMPDIR:-/tmp}/claude-tooling-verify.XXXXXX")}"
mkdir -p "$scratch"
scratch="$(cd "$scratch" && pwd)"
say "scratch dir: $scratch  (model: $MODEL)"

store="$scratch/store/projects/probeproj"
parent="$scratch/probeproj"
rm -rf "$store" "$parent"
mkdir -p "$store/claude/skills/claude-tooling-probe-skill" "$parent"

cat > "$store/claude/skills/claude-tooling-probe-skill/SKILL.md" <<'EOF'
---
name: claude-tooling-probe-skill
description: Probe fixture verifying skill discovery through per-skill symlinks. Never invoke it; it does nothing.
---
This skill exists only so probe sessions can list it.
EOF

# NB the marker must be a VISIBLE line: HTML comments are stripped from
# CLAUDE.md before injection (verified empirically, claude 2.1.221).
cat > "$store/CLAUDE.md" <<'EOF'
# probeproj

Probe fixture project.

PROBE-MARKER: claude-tooling-verify-discovery
EOF

ln -s "$store/CLAUDE.md" "$parent/CLAUDE.md"
mkdir -p "$parent/.claude/skills"
ln -s "$store/claude/skills/claude-tooling-probe-skill" \
      "$parent/.claude/skills/claude-tooling-probe-skill"

mkdir -p "$parent/main"
( cd "$parent/main" \
  && git init -q -b main . \
  && echo probe > README \
  && git add README \
  && git -c user.email=probe@localhost -c user.name=probe commit -qm probe )
printf '/.claude\n' >> "$parent/main/.git/info/exclude"
( cd "$parent/main" && git worktree add -q -b wt1 ../worktrees/wt1 )
ln -s "$parent/.claude" "$parent/main/.claude"
ln -s "$parent/.claude" "$parent/worktrees/wt1/.claude"

probe() { ( cd "$1" && claude --model "$MODEL" -p "$2" < /dev/null 2>&1 ); }

run_case() { # run_case <label> <cwd>
  local label="$1" cwd="$2" out
  say "[$label] asking for skill list …"
  out="$(probe "$cwd" 'Output only the names of your available skills, one per line. No other text.')"
  printf '%s\n' "$out" | sed 's/^/      /'
  if printf '%s' "$out" | grep -q 'claude-tooling-probe-skill'; then
    ok "[$label] skill visible through per-skill symlink"
  else
    fail "[$label] skill NOT visible through per-skill symlink"
  fi
  say "[$label] asking for CLAUDE.md marker …"
  out="$(probe "$cwd" 'Output every line of your context that contains the string PROBE-MARKER, verbatim. If there are none, output exactly NONE.')"
  printf '%s\n' "$out" | sed 's/^/      /'
  if printf '%s' "$out" | grep -q 'claude-tooling-verify-discovery'; then
    ok "[$label] symlinked parent CLAUDE.md loaded via ancestor traversal"
  else
    fail "[$label] symlinked parent CLAUDE.md NOT loaded"
  fi
}

run_case worktree "$parent/worktrees/wt1"
run_case main-checkout "$parent/main"

say "claude version: $(claude --version 2>/dev/null | head -1)"
summary "verify-discovery" || exit 1
