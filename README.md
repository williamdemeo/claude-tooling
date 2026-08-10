<!-- File: README.md -->

# claude-tooling

This repository contains the versioned *source of truth* for @williamdemeo's Claude
Code configuration.

It consists of a global config plus per-project configs, with every project treated
uniformly.

It contains an installer that symlinks everything into place, and documentation of
the multi-project git + Claude workflows.

**Dotfiles-style**.  This repo holds the files; the live locations are symlinks.

**Catastrophe recovery**.  Fresh machine → clone → `make install`→ works (see [docs/recovery.md](docs/recovery.md)).

## The placement principle

Claude config committed *inside* a repo is reserved for config aimed at that
repo's *consumers*.

For example, the `williamdemeo/github-project` template ships `.claude/skills`
teaching its users the workflow; that's product config.

Config that encodes @williamdemeo's workflow lives here, in the claude-tooling
repository, and reaches each project via symlinks.

**One deliberate exception**.  It seems that, at the time of this writing, if a
config is needed by a repo's  *remote session* (e.g., a fresh Claude Code container
in the web ui, where symlinks and parent dirs don't exist) that's only possible if
the config is committed in that repo.

Whether a project keeps such config committed is a per-project decision recorded in
`projects.toml` (`mode = "committed"`), never a default.

## Layout

    projects.toml            manifest: one entry per project (parent dir, main
                             checkout, mode) — drives every script
    install.sh               deploy all symlinks (idempotent, --dry-run, --force)
    Makefile                 install / check / probe / list / verify-discovery
    scripts/                 shared lib + link-worktrees, add-project, lint, probe
    global/                  ~/.claude tier: CLAUDE.md + skills/<name>/
    projects/<p>/CLAUDE.md   project instructions (symlinked to <parent>/CLAUDE.md)
    projects/<p>/claude/     project .claude members: skills/<name>/, hooks/, …
    docs/                    architecture, workflows, migration runbook, recovery

## The uniform per-project pattern

For each project `~/git/<org>/<proj>/` with a main checkout (`main/` or
`master/`) and worktrees beside it:

    ~/git/<org>/<proj>/CLAUDE.md          → projects/<p>/CLAUDE.md   (symlink)
    ~/git/<org>/<proj>/.claude/           real dir (machine-local state stays out
      |                                   of this repo; settings.local.json etc.)
      ├─ skills/<name>                    → projects/<p>/claude/skills/<name>
      └─ <member: hooks/, settings.json>  → projects/<p>/claude/<member>
    <main>/.claude and every worktree root's .claude
                                          → ~/git/<org>/<proj>/.claude
    plus a /.claude line in the shared .git/info/exclude

### Why this shape

Each rule is verified empirically: `make verify-discovery` re-checks them; see
[docs/architecture.md](docs/architecture.md).

+  **Skills** are discovered only from `.claude/skills/` at the session's worktree
   root, so every worktree needs the root symlink; per-skill links are followed.
+  **CLAUDE.md** ancestor traversal crosses the worktree boundary, so one symlinked
   file at the parent covers the main checkout and all worktrees.
+  **settings/settings.local.json** resolve through worktrees to the main checkout,
   whose `.claude` is the parent dir, kept a  *real* directory so local state never
   lands in this repo.

## Usage

    make install                    # everything (or PROJECT=fls, PROJECT=global)
    make install DRY_RUN=1          # show what would change
    make install FORCE=1            # may replace real files (backed up first)
    make check                      # static verification, zero tokens
    make probe                      # live claude -p matrix (costs tokens, opt-in)
    make list                       # skill inventory by tier
    scripts/link-worktrees.sh fls   # backfill .claude links over new worktrees
    scripts/add-project.sh org/name # scaffold the next project

`install.sh` is idempotent, never replaces a real (non-symlink) file without `--force`
(originals go to `~/.local/state/claude-tooling/backups/<ts>/…`), and always skips
checkouts where `.claude` is *tracked* content (transitional repos, pre-removal-PR).

## Projects

| project                | parent                                      | mode      | status                                                            |
|------------------------|---------------------------------------------|-----------|-------------------------------------------------------------------|
| fls                    | `~/git/IO/fls`                              | symlink   | **migrated (2026-08-09)**; live config is symlinks into this repo |
| agda-algebras          | `~/git/ualib/agda-algebras`                 | symlink   | absorbed; committed config still in repo (stage 3/4)              |
| agda-native-air        | `~/git/formalverification/agda-native-air`  | symlink   | absorbed; committed config still in repo (stage 3/4)              |
| williamdemeo.github.io | `~/git/williamdemeo/williamdemeo.github.io` | symlink   | scaffolded; checkout confirmed; skills TBD                        |
| github-project         | `~/git/williamdemeo/github-project`         | committed | product config; installer never touches it                        |

Migration stages, current state, and the exact commands per stage are documented in
[docs/migration.md](docs/migration.md).
