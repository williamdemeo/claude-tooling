# The multi-project worktree workflow

Every project follows the same layout (manifest: `projects.toml`):

    ~/git/<org>/<proj>/
      <main>/          the ONLY place for fetch, pull, and `git worktree add`
                       (main or master — see the manifest); never does branch work
      worktrees/…      one worktree per branch (fls grew several container
                       dirs — william/, carlos/, claude/, … — the tooling
                       follows `git worktree list`, not directory names)
      CLAUDE.md        → claude-tooling (loads in every session under <proj>/)
      .claude/         real dir; skills/<name> → claude-tooling
      .mcp.json        → claude-tooling — only for projects with a
                         projects/<p>/mcp.json there (agda-algebras,
                         agda-native-air); each checkout root gets a
                         .mcp.json → parent link too

## New-worktree ritual

From the main checkout:

    git worktree add -b <branch> ../worktrees/<branch> origin/<branch>
    ~/git/williamdemeo/claude-tooling/main/scripts/link-worktrees.sh <project>

`link-worktrees.sh` backfills the root `.claude` symlink over every
worktree the main checkout knows about (idempotent — run it any time), and
keeps the `/.claude` line in the shared `.git/info/exclude`. For projects
with a managed mcp.json it backfills the root `.mcp.json` link and the
`/.mcp.json` exclude line the same way. Claude-web branches (`claude/*`)
that get checked out locally afterwards need the same backfill — one more
reason the script re-runs over everything.

**Launch `claude` from the checkout root** in mcp-managed projects: MCP
servers spawn with cwd = the launch directory, and `${PWD}` in the config
expands there too (discovery rules 8–10, docs/architecture.md) — so
agda-algebras' library registration and air's relative `command` path both
resolve to the right checkout only from its root.

## Cautions that have bitten before

- **Rewritten branch histories** (routine in fls): before any
  `git reset --hard origin/<branch>`, check
  `git cherry origin/<branch> HEAD` — every line `-` ⇒ nothing local is
  lost. (From the fls conventions; applies anywhere histories get rebased.)
- **`git clean -fdx` deletes the `.claude` symlink** — excluded counts as
  ignored, and `-x` removes ignored files. Only the link is lost (the repo
  is elsewhere); re-run `link-worktrees.sh`. Plain `git clean -fd` without
  `-x` leaves it alone.
- **Moving a checkout breaks its worktrees**: worktree metadata stores
  absolute paths (this happened to williamdemeo.github.io when it moved out
  of the MKDOCS dir — every worktree went `prunable`). `git worktree
  repair`, or prune and re-add.
- **Stale worktrees accumulate** (fls peaked at 105, agda-algebras at 127;
  73 fls branches tracked upstreams already deleted at origin). Cleanup is
  its own careful task: see `docs/kickoffs/fls-worktree-cleanup.md`.

## Who creates worktrees where (fls specifics)

From the fls conventions: William's worktrees carry unprefixed branch
names; Carlos's are usually `carlos/`-prefixed; Claude-web sessions create
`claude/`-prefixed branches. Small commits with clear messages; Claude's
commits carry the Co-Authored-By trailer, William's standalone tidy-ups
don't.
