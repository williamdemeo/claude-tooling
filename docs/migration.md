<!-- File: docs/migration.md -->

# Migration runbook and status

**Live state and the exact commands per stage**.

Every mutating stage needs @williamdemeo's explicit yes first.

`make check` is safe at every point and reports pending items as warnings, errors
only for genuine breakage.

## Status (2026-08-09)

| stage | scope                                                            | state                                          |
|-------|------------------------------------------------------------------|------------------------------------------------|
| 1     | repo skeleton + installer + `make check` on COPIES of all config | **done 2026-08-09** (live locations untouched) |
| 2     | fls: replace live parent files with symlinks                     | **done 2026-08-09** `install.sh --force fls`, 0 errors; `make check` green; live probe 14/14; backups: `~/.local/state/claude-tooling/backups/20260809-105419/` |
| 3     | agda-algebras + air: install parent config alongside committed   | **done 2026-08-13** (William drove it): install clean, `make check` green, live probes 16/16 both projects (after fixing a probe substring-matching bug); transitional tracked-`.claude` remains in 4 aa checkouts + air's main until stage 4 |
| 4     | removal PRs in agda-algebras + air                               | **PRs open 2026-08-13, awaiting William's merge**: ualib/agda-algebras#532, formalverification/agda-native-air#90 (scope: CLAUDE.md + .claude; web sessions run bare until env setup scripts land — option (e)-lite) |
| 5     | global: replace ~/.claude/CLAUDE.md + 2 skills with symlinks     | ready: awaiting yes |

**Post-stage-2 state**.

+  **fls**.  102/105 worktrees linked (3 old `claude/*` branches still
   carry tracked `.claude`; skipped by design), exclude line present, parent
   CLAUDE.md + all 4 skills are symlinks into this repo; agda-algebras 94 of 127
   worktrees carry tracked `.claude`;

+  **agda-native-air**.  A single fresh `main` checkout;

+  **williamdemeo.github.io**.  Checkout confirmed by William
   (`~/git/williamdemeo/williamdemeo.github.io`), its 23 broken worktree registrations
   (moved out of the old MKDOCS path) still pending `git worktree repair` or prune.

## The web-container conflict (stage 4 decision)

Claude Code on the web sees only *committed* config.  The agda-algebras and
agda-native-air `.claude/hooks/session-start.sh` exist specifically to provision web
containers, and `claude/*` branches show real web usage.  The kickoff's "absorb then
remove" decision therefore breaks web sessions for those two repos in proportion to
what gets removed.

**Options per repo**. 

+  **(a) remove everything** (kickoff's letter): web sessions run bare.
+  **(b) remove CLAUDE.md + skills, keep hooks + settings.json**: web sessions keep a
   working toolchain but lose guidance/skills. 
+  **(c) keep everything committed** (`mode = "committed"` in the manifest):
   claude-tooling drops its copies; the repo stays the source of truth for its own
   config (it *is* versioned there).
+  **(d) both worlds**: claude-tooling stays the source of truth and a small sync
   script keeps the committed copies current (adds drift tooling; only worth it if
   web usage of these repos is heavy).
+  **(e) remove everything + web-environment setup script** (gated on experiment iii,
   docs/terminal-vs-web.md): like (a), but each repo's web environment runs a setup
   script that provisions the toolchain and installs skills + CLAUDE.md into the
   container's `~/.claude` from claude-tooling — the fls pattern
   (`projects/fls/web-environment/`) applied to agda-algebras/agda-native-air.  If
   the experiments succeed this dominates (a)–(d): one source of truth, nothing
   committed, web sessions fully served.

**Recommendation**. Decide per repo after interview question 2
(docs/terminal-vs-web.md) and the experiment results: **(e) if the experiments pass**,
else per repo among (b)/(c)/(d).

Absent (e), agda-native-air looks like the strongest case for (b) or (c); the kickoff
itself anticipated agda-native-air might deliberately keep a committed CLAUDE.md.

**Research note** (2026-08-09, see docs/terminal-vs-web.md findings).

Committed-in-repo is the only *fully* verified way web sessions get skills today;
claude.ai org-skill uploads target chat/Cowork (docs say not Claude Code, but the new
web env-config skills picker is undocumented; verify empirically).

Cloud-environment setup scripts can verifiably fetch skills into the container, which
could serve even fls web sessions without committing anything to the IOG repo.

This tilts aa/air toward options (b)/(c)/(d) rather than (a).

## Stage 2: fls

fls is the only project whose live config has no other home.

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

**Rollback**.  For each path, `rm <link> && mv <backup>/<path> <path>`.

**Post-stage cleanup**.

Done 2026-08-09: `~/git/IO/fls/dot-claude/` is archived verbatim at
`projects/fls/attic/dot-claude/` (see the attic README for what each file is, and why
the hook matters for the future fls cloud-environment setup script).  Its
`session-start.sh` was the newest revision anywhere — the copy tracked on branch
`claude/agda-skill-and-session-hook` (local + origin) is ~13 lines older.  The
original dir can now be deleted at William's leisure:
`rm -r ~/git/IO/fls/dot-claude`.

## Stage 3: agda-algebras and agda-native-air

This is the parent-level config (additive).

**Manual runbook** (driven by @williamdemeo).

Stage 3 *replaces nothing*; it only creates new symlinks and two small real dirs at
the parent level, next to the still-committed config.

All commands are invoked from `~/git/williamdemeo/claude-tooling/main`.

**1. Review what will start loading**.

The parent `CLAUDE.md` loads in every session under each project dir, in addition to
the committed one.

    diff -u ~/git/ualib/agda-algebras/master/CLAUDE.md projects/agda-algebras/CLAUDE.md
    #   expect ONLY additions: “Library policy”, “Review workflow”,
    #   “Claude config for this project”, PROBE-MARKER line
    diff -u ~/git/formalverification/agda-native-air/main/CLAUDE.md projects/agda-native-air/CLAUDE.md
    #   expect ONLY: “Claude config for this project” + PROBE-MARKER
    diff -ru ~/git/ualib/agda-algebras/master/.claude/skills projects/agda-algebras/claude/skills
    diff -ru ~/git/ualib/agda-algebras/master/.claude/hooks  projects/agda-algebras/claude/hooks
    diff -u  ~/git/ualib/agda-algebras/master/.claude/settings.json projects/agda-algebras/claude/settings.json
    diff -ru ~/git/formalverification/agda-native-air/main/.claude/skills projects/agda-native-air/claude/skills
    diff -ru ~/git/formalverification/agda-native-air/main/.claude/hooks  projects/agda-native-air/claude/hooks
    diff -u  ~/git/formalverification/agda-native-air/main/.claude/settings.json projects/agda-native-air/claude/settings.json
    #   all six: expect NO output (byte-identical copies)

**2. Dry-run, then read the recap at the bottom:**

    ./install.sh --dry-run agda-algebras agda-native-air

Expected: `→` planned lines (parent CLAUDE.md, per-skill links, hooks,
settings.json, .claude dirs, exclude append, worktrees without tracked
.claude) and `!` tracked-content skips (~94 in agda-algebras, incl. the
master checkout itself; air’s single main checkout likewise).  You do NOT
need to scan all of it: anything that needs investigation prints as red
`!!` and is recapped verbatim in a **NEEDS ATTENTION** section at the end
of the run.  Proceed only when that section is absent (or you have
resolved each item).

**3. Install (deliberately WITHOUT --force**, so any surprise is skipped
and reported instead of replaced):

    ./install.sh agda-algebras agda-native-air

**4. Verify:**

    make check PROJECT=agda-algebras     # 0 errors; warnings = tracked-transitional only
    make check PROJECT=agda-native-air
    make probe PROJECT=agda-algebras     # live: 4+2 skills, own marker, no leakage
    make probe PROJECT=agda-native-air   # live: 2+2 skills, own marker, no leakage
    git status --short                   # claude-tooling itself must stay CLEAN
                                         # (no settings.local.json creeping in)

Optionally eyeball a real session: run `claude` in an agda-algebras
worktree, `/context` should show the parent CLAUDE.md content (e.g. the
“Library policy” section), and the skills list its 4 project skills.

**What stage 3 does NOT change:** settings and hooks still come from the
COMMITTED `.claude` (settings resolve to the MAIN checkout, whose .claude
is the tracked real dir until stage 4); the parent-level settings.json
and hooks links are dormant until then. `settings.local.json`
(`enabledMcpjsonServers`) stays untouched in `master/.claude/`.

**Transitional wrinkle** (expected, harmless): until stage 4 lands,
sessions load BOTH the committed CLAUDE.md and the parent-level one —
near-identical content; the parent copy adds the merged draft sections
and the config-placement section. Skills resolve from the tracked
.claude where it exists — same skill set either way.

**Rollback** (stage 3 created only links + two dirs of links; committed
config was never touched):

    rm ~/git/ualib/agda-algebras/CLAUDE.md
    rm -r ~/git/ualib/agda-algebras/.claude
    rm ~/git/formalverification/agda-native-air/CLAUDE.md
    rm -r ~/git/formalverification/agda-native-air/.claude
    # (worktree .claude links and the exclude lines are harmless either way)

**Afterwards**, once the merge in projects/agda-algebras/CLAUDE.md is
confirmed faithful: delete the untracked
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

Side-finding, CORRECTED 2026-08-13: agda-algebras' `.mcp.json` (registers
the `agda` MCP server from air) was never tracked in that repo — it is
untracked, machine-local config that sat with a stale absolute path until
William fixed it. Its durable home is this repo via per-worktree symlinks:
claude-tooling issue #3, to be implemented in ct.py after the port (PR #2)
merges. Until then it lives untracked in the master checkout only.

## Stage 5 — global

    diff -u ~/.claude/CLAUDE.md global/CLAUDE.md
    #    expect: placement parenthetical now names this repo + PROBE-MARKER
    for s in agda-ring-solver git-thematic-squash worktree-forest-cleanup; do
      diff -ru ~/.claude/skills/$s global/skills/$s
    done
    #    expect: no output — unless a live skill was edited after its
    #    absorption; if so, decide which side wins BEFORE --force (the
    #    backup keeps the live version either way)
    ./install.sh --dry-run --force global
    ./install.sh --force global
    make check PROJECT=global ; make probe PROJECT=global

`~/.claude/settings.json` stays unmanaged for now (open question: absorb
into global/ later — it carries cleanupPeriodDays, model, effort,
permissions).
