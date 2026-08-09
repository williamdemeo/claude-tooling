# Architecture

## The placement principle

Claude config committed INSIDE a repo is reserved for config aimed at that
repo's **consumers** (e.g. the `williamdemeo/github-project` template ships
`.claude/skills` teaching its users the workflow — that's product config).
Config that encodes **William's workflow** lives here, in claude-tooling,
and reaches each project via symlinks.

**The web-container exception.** Claude Code on the web clones a repo into
a fresh container: no parent dirs, no symlinks, no `~/.claude`. The ONLY
config a web session can see is what is committed in the repo. So config a
repo's remote sessions genuinely need (e.g. a SessionStart hook that
provisions Nix, the CLAUDE.md build/test guidance) can serve "the repo's
consumers" even when the consumer is William-on-the-web. Whether a project
keeps such config committed is a per-project decision recorded in
`projects.toml` (`mode = "committed"`), made deliberately — never by
default.

## Discovery rules (empirical)

Everything here was verified with probe fixtures and fresh `claude -p`
sessions; re-verify with `make verify-discovery` if anything seems off —
behavior may change across Claude Code versions.

Verified 2026-08-08 (design inputs):

1. **Skills** are discovered ONLY from `.claude/skills/` at the session's
   start directory up to the FIRST `.git` (the worktree root). Ancestor
   directories above that are NOT searched; the main checkout is NOT
   searched from a worktree. A SYMLINKED `.claude` at the worktree root IS
   followed. `~/.claude/skills` always loads.
2. **CLAUDE.md** ancestor traversal from cwd DOES cross the worktree
   boundary (a file at `~/git/IO/fls/CLAUDE.md` loads in every fls worktree
   session). The main checkout's own CLAUDE.md does NOT load into worktree
   sessions. `~/.claude/CLAUDE.md` always loads.
3. **settings.json / settings.local.json and auto-memory** resolve through
   worktrees to the MAIN checkout (documented Claude Code behavior).

Verified 2026-08-09 on claude 2.1.221 (`scripts/verify-discovery.sh`, this
repo's deployment shape):

4. **Per-skill symlinks are followed**: worktree-root `.claude` symlink →
   parent real dir → `skills/<name>` symlink → this repo. Works from
   worktrees and the main checkout.
5. **A symlinked parent-level CLAUDE.md loads** via ancestor traversal.
6. **HTML comments are STRIPPED from CLAUDE.md** before injection — probe
   markers must be visible text lines (`PROBE-MARKER: …`).
7. An absolute-path `@import` in a parent-level CLAUDE.md did NOT load in
   the fixture. Nothing in this design uses `@imports`; do not rely on
   them here without re-verifying.

## The uniform per-project pattern

For each project `~/git/<org>/<proj>/` (manifest: `parent`) with main
checkout `<parent>/<main>` and worktrees wherever `git worktree list` says
they are:

    <parent>/CLAUDE.md              → <repo>/projects/<p>/CLAUDE.md
    <parent>/.claude/               REAL directory
      skills/<name>                 → <repo>/projects/<p>/claude/skills/<name>
      <member: hooks/, settings.json>
                                    → <repo>/projects/<p>/claude/<member>
    <main>/.claude, <each worktree>/.claude
                                    → <parent>/.claude
    <main .git>/info/exclude        gains a /.claude line (shared by all
                                    linked worktrees; exclude only affects
                                    untracked files, so it is safe to add
                                    even while a repo still tracks .claude)

Rule 2 makes the parent CLAUDE.md cover the main checkout and every
worktree; rule 1 is why every worktree root needs the `.claude` symlink;
rule 3 is why the parent `.claude` must stay a REAL directory:
`settings.local.json` (and any other machine-local state Claude Code writes
under the main checkout's `.claude`, which resolves here) must live outside
this repo. The evidence case: agda-algebras' committed `.claude` acquired
an untracked `settings.local.json` (`enabledMcpjsonServers`) — under a
whole-dir symlink that file would have landed in this repo.

## Design decisions

- **Per-skill symlinks** (both `~/.claude/skills/` and project skills), not
  whole-directory links: leaves room for unmanaged local scratch skills
  next to managed ones. Cost: a new repo skill needs one `make install` to
  go live; `make check` flags unlinked skills.
- **Absolute symlink targets**, matching the pre-existing fls convention
  (`/home/williamdemeo/git/IO/fls/.claude`). Single-machine layout is the
  contract; the manifest records it.
- **No `worktrees` field in the manifest**: fls keeps worktrees under a
  dozen different container dirs; a manifest list would be a lie waiting to
  happen. `git worktree list --porcelain` in the main checkout is the
  source of truth, and `scripts/link-worktrees.sh` trusts only it.
- **Live config follows the canonical checkout** (`meta.canonical_root`,
  i.e. this repo's `main`). Running install.sh from another worktree warns
  loudly, because links would point at that worktree.
- **Backups are central** (`~/.local/state/claude-tooling/backups/<ts>/…`,
  mirroring absolute paths), never `*.bak` siblings that would show up as
  untracked files in checkouts.
- **Tracked `.claude` is never touched**, even under `--force`: replacing
  tracked content would dirty a checkout. The installer skips and reports
  those worktrees (transitional state until a removal PR lands).
- **bash + coreutils + awk (+ python3-stdlib for lint only)**, no flake:
  this repo is the thing reached for during recovery, so it must run
  before any toolchain exists. The manifest is a restricted TOML subset
  for the same reason (see the header comment in `projects.toml`).

## The manifest

`projects.toml` — see its header comment for the format. One stanza per
project: `parent`, `main`, `mode` (`symlink` | `committed`). `[meta]
canonical_root` anchors the warning above. `scripts/add-project.sh
<org>/<name>` scaffolds a new stanza plus the `projects/<name>/` skeleton.
