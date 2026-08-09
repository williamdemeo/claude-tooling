# Migration runbook and status

Live state and the exact commands per stage. Every mutating stage needs
William's explicit yes first. `make check` is safe at every point and
reports pending items as warnings, errors only for genuine breakage.

## Status (2026-08-09)

| stage | scope | state |
|-------|-------|-------|
| 1 | repo skeleton + installer + `make check` on COPIES of all config | **done** (this repo; live locations untouched) |
| 2 | fls: replace live parent files with symlinks | ready — awaiting yes |
| 3 | agda-algebras + air: install parent-level config alongside committed config | ready — awaiting yes; see the web-container conflict below |
| 4 | removal PRs in agda-algebras + air | **blocked on a design decision** (below) |
| 5 | global: replace ~/.claude/CLAUDE.md + 2 skills with symlinks | ready — awaiting yes |

Baseline check output today: fls 101/105 worktrees already linked, 3 with
tracked `.claude` (old `claude/*` branches), exclude line present;
agda-algebras 94 of 127 worktrees carry tracked `.claude`; air is a single
fresh `main` checkout; website has 23 broken worktree registrations
(moved out of the old MKDOCS path — `git worktree repair` or prune).

## The web-container conflict (stage 4 decision)

Claude Code on the web sees only COMMITTED config. The agda-algebras and
air `.claude/hooks/session-start.sh` exist specifically to provision web
containers, and `claude/*` branches show real web usage. The kickoff's
"absorb then remove" decision therefore breaks web sessions for those two
repos in proportion to what gets removed. Options per repo:

- **(a) remove everything** (kickoff's letter): web sessions run bare.
- **(b) remove CLAUDE.md + skills, keep hooks + settings.json**: web
  sessions keep a working toolchain but lose guidance/skills.
- **(c) keep everything committed** (`mode = "committed"` in the
  manifest): claude-tooling drops its copies; the repo stays the source
  of truth for its own config (it *is* versioned there).
- **(d) both worlds**: claude-tooling stays the source of truth and a
  small sync script keeps the committed copies current (adds drift
  tooling; only worth it if web usage of these repos is heavy).

Recommendation: decide per repo after interview question 2
(docs/terminal-vs-web.md) — air looks like the strongest case for (b) or
(c); the kickoff itself anticipated air might deliberately keep a
committed CLAUDE.md.

## Stage 2 — fls (the only project whose live config has no other home)

    cd ~/git/williamdemeo/claude-tooling/main
    # 1. preview the deltas the migration will make live:
    diff -u ~/git/IO/fls/CLAUDE.md projects/fls/CLAUDE.md
    #    expect: rewritten "Claude config for this project" + PROBE-MARKER
    diff -ru ~/git/IO/fls/.claude/skills projects/fls/claude/skills
    #    expect: agda-typecheck description typo fix only
    # 2. dry-run, then migrate (originals → ~/.local/state/claude-tooling/backups/<ts>/…):
    ./install.sh --dry-run --force fls
    ./install.sh --force fls
    # 3. verify:
    make check PROJECT=fls        # every fls item ✓
    make probe PROJECT=fls        # live: 4 skills + marker, no leakage

Rollback: for each path, `rm <link> && mv <backup>/<path> <path>`.

Post-stage cleanup (William's call): `~/git/IO/fls/dot-claude/` is a stale
pre-removal snapshot (old fls-specific agda-typecheck skill + the old
session hook + settings.json). Archive or delete once stage 2 is green.

## Stage 3 — agda-algebras and air (parent-level config, additive)

    ./install.sh agda-algebras agda-native-air      # no --force needed:
    # parent CLAUDE.md/.claude don't exist yet; worktrees with tracked
    # .claude are skipped and reported (94 in agda-algebras today)
    make check PROJECT=agda-algebras ; make probe PROJECT=agda-algebras
    make check PROJECT=agda-native-air ; make probe PROJECT=agda-native-air

Transitional wrinkle (expected, harmless): until stage 4 lands, worktree
sessions load BOTH the committed CLAUDE.md and the parent-level one
(near-identical content; the parent copy adds the merged draft sections
and the config-placement section). Skills resolve from the tracked
.claude in those worktrees — same skill set either way.

Also in this stage, after confirming the merge in projects/agda-algebras/
CLAUDE.md is faithful: delete the untracked
`~/git/ualib/agda-algebras/master/CLAUDE-draft-additions.md`.

## Stage 4 — removal PRs (after the web decision)

Per repo, on a branch: `git rm -r` whatever the decision says (see options
above), README pointer if appropriate; William approves and merges. After
merge, each worktree only loses its tracked .claude when ITS checkout
updates — strongly consider the worktree cleanups first
(docs/kickoffs/fls-worktree-cleanup.md; agda-algebras deserves the same
treatment, 127 worktrees) so the re-link pass touches a dozen worktrees,
not a hundred. Then:

    scripts/link-worktrees.sh agda-algebras agda-native-air

Side-finding for the same PRs: agda-algebras' committed `.mcp.json` points
at a stale absolute path (`~/git/AI/PROJECTS/agda-native-air/…` — air
lives in `~/git/formalverification/` now) and at William's home dir, so it
is broken for other consumers anyway; decide whether it should be fixed,
removed, or left.

## Stage 5 — global

    diff -u ~/.claude/CLAUDE.md global/CLAUDE.md
    #    expect: placement parenthetical now names this repo + PROBE-MARKER
    ./install.sh --dry-run --force global
    ./install.sh --force global
    make check PROJECT=global ; make probe PROJECT=global

`~/.claude/settings.json` stays unmanaged for now (open question: absorb
into global/ later — it carries cleanupPeriodDays, model, effort,
permissions).
