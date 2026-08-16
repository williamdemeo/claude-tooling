# Architecture

## The placement principle

Claude config committed INSIDE a repo is reserved for config aimed at that repo's
**consumers**, e.g., the `williamdemeo/github-project` template ships
`.claude/skills` teaching its users the workflow (that's product config).

Config that encodes *William's workflow* lives here, in claude-tooling, and reaches
each project via symlinks.

**The web-container exception**.

Claude Code on the web clones a repo into a fresh container: no parent dirs, no
symlinks, no `~/.claude`.

The ONLY config a web session can see is what is committed in the repo.  So config a
repo's remote sessions genuinely need (e.g. a SessionStart hook that provisions Nix,
the CLAUDE.md build/test guidance) can serve "the repo's consumers" even when the
consumer is William-on-the-web.  Whether a project keeps such config committed is a
per-project decision recorded in `projects.toml` (`mode = "committed"`), made
deliberately, never by default.

## Discovery rules (empirical)

Everything here was verified with probe fixtures and fresh `claude -p` sessions;
re-verify with `make verify-discovery` if anything seems off.  Behavior may change
across Claude Code versions.

**Verified 2026-08-08** (design inputs).

1.  **Skills** are discovered ONLY from `.claude/skills/` at the session's start
    directory up to the FIRST `.git` (the worktree root).  Ancestor directories
    above that are NOT searched; the main checkout is NOT searched from a worktree.
    A SYMLINKED `.claude` at the worktree root *is* followed.
    `~/.claude/skills` always loads.

2.  **CLAUDE.md** ancestor traversal from cwd *does* cross the worktree boundary
    (a file at `~/git/IO/fls/CLAUDE.md` loads in every fls worktree session)
    The main checkout's own CLAUDE.md does *not* load  into worktree sessions.
    `~/.claude/CLAUDE.md` always loads.

3.  **settings.json / settings.local.json and auto-memory** resolve through worktrees
    to the *main* checkout (documented Claude Code behavior).

**Verified 2026-08-09 on claude 2.1.221**
(`scripts/verify-discovery.sh`, this repo's deployment shape).

4.  **Per-skill symlinks are followed**: worktree-root `.claude` symlink
    → parent real dir → `skills/<name>` symlink → this repo;
    works from worktrees and the main checkout.

5.  **A symlinked parent-level CLAUDE.md loads** via ancestor traversal.

6.  **HTML comments are STRIPPED from CLAUDE.md** before injection; probe markers
    must be visible text lines (`PROBE-MARKER: …`).

7.  An absolute-path `@import` in a parent-level CLAUDE.md did *not* load in the
    fixture.  Nothing in this design uses `@imports`; do not rely on them here without
    re-verifying.

**Verified 2026-08-14 on claude 2.1.221**
(`.mcp.json` design inputs).

8.  **A project-root `.mcp.json` may be a SYMLINK**: a two-hop chain
   (checkout root → parent → this repo, final target outside the
   checkout) is discovered, parsed, approvable, and its servers LAUNCH,
   identically to a real file. Discovery also works from a subdirectory
   of the checkout.

9.  **`${VAR}` (and `${VAR:-default}`) expands in `.mcp.json` env values**
    when the server launches — *not* at parse time (`claude mcp list` shows
    the raw config for a pending server). `${CLAUDE_PROJECT_DIR}` is *not*
    set at MCP launch; do not use it there.

10. **MCP stdio servers spawn with cwd = the directory `claude` was
    launched from** — not a normalized project root — and `${PWD}` expands
    to that same directory. So a relative `command` and a `${PWD}` env
    value both resolve per checkout, PROVIDED sessions start at the
    checkout root (launching from a subdirectory shifts both).

Fixture procedure for 8–10, zero-to-few tokens: a scratch git checkout
whose `.mcp.json` (behind the parent→repo symlink chain) registers a
dummy stdio server — a python script that appends its `os.getcwd()` and
probe env vars to a log, then answers `initialize`. `claude mcp list`
from the checkout proves discovery (the server is listed with its parsed
command even while ⏸ pending approval, spending no tokens); to see the
launch-layer facts, pre-approve it with `{"enableAllProjectMcpServers":
true}` in the fixture's `.claude/settings.local.json` and run one tiny
`claude -p` there, then read the log.

## The uniform per-project pattern

For each project `~/git/<org>/<proj>/` (manifest: `parent`) with main
checkout `<parent>/<main>` and worktrees wherever `git worktree list` says
they are:

    <parent>/CLAUDE.md              → <repo>/projects/<p>/CLAUDE.md
    <parent>/.mcp.json              → <repo>/projects/<p>/mcp.json
                                    (only if that repo file exists;
                                    presence-driven, like every mcp piece)
    <parent>/.claude/               REAL directory
      skills/<name>                 → <repo>/projects/<p>/claude/skills/<name>
      <member: hooks/, settings.json>
                                    → <repo>/projects/<p>/claude/<member>
    <main>/.claude, <each worktree>/.claude
                                    → <parent>/.claude
    <main>/.mcp.json, <each worktree>/.mcp.json
                                    → <parent>/.mcp.json
    <main .git>/info/exclude        gains a /.claude line, and /.mcp.json
                                    when managed (shared by all linked
                                    worktrees; exclude only affects
                                    untracked files, so it is safe to add
                                    even while a repo still tracks .claude)

Rule 2 makes the parent CLAUDE.md cover the main checkout and every
worktree; rule 1 is why every worktree root needs the `.claude` symlink
(and `.mcp.json` is read per checkout root, so it needs the same
per-checkout link); rule 8 is why one repo mcp.json can serve every
checkout through the two-hop chain, and rules 9–10 are what let a shared
file carry per-checkout values (`${PWD}`); see the agda-algebras entry.
Rule 3 is why the parent `.claude` must stay a REAL directory:
`settings.local.json` (and any other machine-local state Claude Code writes
under the main checkout's `.claude`, which resolves here) must live outside
this repo. The evidence case: agda-algebras' committed `.claude` acquired
an untracked `settings.local.json` (`enabledMcpjsonServers`); under a
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
- **`.mcp.json` is presence-driven and per-member guarded**: a project
  gets the `.mcp.json` tier only if `projects/<p>/mcp.json` exists in this
  repo; nothing is scaffolded, and `check` flags our deployment shape
  wherever its repo source is missing. The tracked-content guard is judged
  per member: a transitional tracked-`.claude` checkout still gets its
  `.mcp.json` link, but a checkout that tracks `.mcp.json` itself is never
  touched. agda-algebras shows why one shared file suffices even for
  per-checkout config: its `env.AGDA_ALGEBRAS_ROOT` is `${PWD}` (rules
  9–10), which resolves to each checkout root as long as sessions launch
  there — the standing ritual anyway, and air's relative `command` path
  has always had the same requirement.
- **git + a POSIX shell + python3 ≥ 3.11 stdlib**, no flake, no pip: this
  repo is the thing reached for during recovery, so it must run before any
  toolchain exists. 3.11 is the floor because `tomllib` parses the
  manifest, which is therefore plain TOML with no subset caveats.
- **One module, `scripts/ct.py`, with subcommands**; `install.sh` and the
  `scripts/*.sh` names are two-line shims into it, so every documented
  command still works verbatim. Ported from ~900 lines of bash: `set -e`'s
  function-return semantics had already shipped one real bug, `probe.sh`'s
  `comm`-based set arithmetic was unreadable, and the awk TOML-subset
  parser was the price of having no real one. The no-dependencies rule is
  unchanged; it was never a pro-bash rule. `make test` runs the unit
  suite (tmp fixtures only; it never touches live config).

## The manifest

`projects.toml`: plain TOML; see its header comment. One stanza per
project: `parent`, `main`, `mode` (`symlink` | `committed`). `[meta]
canonical_root` anchors the warning above. `scripts/add-project.sh
<org>/<name>` scaffolds a new stanza plus the `projects/<name>/` skeleton.
