<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-7-mcpjson-management.md
     (authored 2026-08-14 for issue #3). Launch a fresh session from the
     issue worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-7-mcpjson-management.md` -->

# Kick-off: manage project-root `.mcp.json` files (issue #3)

You are starting fresh, with no memory of the sessions that designed this
repo. Everything you need is in this prompt, the referenced paths, and
GitHub issue #3 — read the issue in full first (`gh issue view 3`). Push
back where the design seems wrong; William explicitly wants that. Nothing
that mutates state outside your worktree happens without his explicit yes.

## Mission

MCP server registrations live in `.mcp.json` at a checkout root, and
Claude Code reads them per-directory — so in a worktree-based layout the
copies proliferate and go stale (a stale-pathed copy sat in agda-algebras'
master checkout until William fixed it by hand on 2026-08-13; three more
stale copies still sit in old worktrees). This work brings `.mcp.json`
under claude-tooling management exactly like `CLAUDE.md` and `.claude`
already are: one versioned copy per project in this repo, one symlink at
the project parent, one symlink per checkout root.

## Where you are

- `williamdemeo/claude-tooling` (PRIVATE) is the versioned source of truth
  for William's Claude config. Read `README.md`, `docs/architecture.md`,
  and `docs/worktree-workflow.md` before designing. The entire
  implementation is `scripts/ct.py` (typed, stdlib-only, python ≥ 3.11;
  `mypy --strict` clean); `scripts/test_ct.py` is its suite (`make test`,
  105 tests green at kickoff time); `install.sh` and `scripts/*.sh` are
  two-line shims.
- You are in the worktree
  `~/git/williamdemeo/claude-tooling/worktrees/3-manage-project-root-mcpjson-files`
  on the branch of the same name. The canonical checkout is
  `~/git/williamdemeo/claude-tooling/main` — never develop there. Work in
  small commits; open a PR to `main`; William reviews and merges.
- CRITICAL: `make check` is NEVER green from a worktree — the live
  symlinks point into `main`, so "symlink to foreign target" errors there
  are `meta.canonical_root` protection working, not a regression. Develop
  against `make test` (pure tmp fixtures); live verification happens
  post-merge, from `main`.

## Measured state (2026-08-14 — re-measure before acting, don't trust)

| location | `.mcp.json` |
|---|---|
| agda-algebras `master/` | present — the FIXED copy (2026-08-13) |
| agda-algebras worktrees 461-…, 502-…, 520-… | present — STALE copies (sizes differ from master's) |
| agda-native-air `main/` | present — modified 2026-08-14, absorb the CURRENT content |
| agda-native-air worktree `sync-scripts-python-utils/` | present — copy from 2026-08-13 |
| fls, williamdemeo.github.io, github-project, claude-tooling | none |

Two corrections to the issue text: worktree copies DO exist (aa's three,
air's one), and agda-algebras is not the only project with the file — air
has one too. Diff every copy against its main-checkout sibling before
absorbing anything; take the union of intent (expect the deltas to be the
stale-path fix, but prove it — nothing gets silently dropped).

## Design (from issue #3 — verify the load-bearing caveat FIRST)

- repo: `projects/<p>/mcp.json` (no leading dot inside the repo, matching
  the `claude/` ↔ `.claude` convention)
- parent: `~/git/<org>/<p>/.mcp.json` → repo copy
- every checkout root (main + each worktree): `.mcp.json` → parent copy
- `/.mcp.json` line in the shared `.git/info/exclude` (same treatment as
  `/.claude`)
- `check` classifies it like any other managed member; `list` shows it
- presence-driven: a project without `projects/<p>/mcp.json` gets nothing;
  committed-mode projects are never touched (existing rule)

**The caveat**: nobody has verified that Claude Code resolves a
*symlinked* project-root `.mcp.json`. Verify it cheaply before writing any
installer code: `claude mcp list` reads the same config resolution and
spends no API tokens — build a scratch fixture (a real `.mcp.json` with a
dummy server vs. the same file behind the parent→repo symlink chain, in a
git checkout) and compare what it reports from each directory. If symlinks
resolve, record the new empirically-verified rule in
`docs/architecture.md`'s list, with the fixture procedure. If they do
NOT, STOP and present alternatives to William (e.g. managed copies with
drift detection in `check`) — the whole design hangs on this.

## Requirements

1. Implement in `scripts/ct.py` only. Anchor points: `install_project`
   (the parent `CLAUDE.md` `ensure_link` is the model), `link_worktrees_for`,
   `check`'s install-state layer, `cmd_list`. Respect the conventions three
   review rounds just hardened: refuse any state that could deploy outside
   the manifest; backups via the existing `backup_move` machinery
   (`--force` semantics unchanged); guards on tracked files are never
   overridden.
2. Match `ct.py`'s existing idiom (`Reporter`/`Fatal`, frozen dataclasses,
   docstrings in its voice) — the `functional-python` skill's `Result` API
   is for the utils-based projects, not this file.
3. `make test` green with new `DeploymentFixture`-style tests: fresh
   install, idempotent re-run, worktree linking, `--force` swap of a
   pre-existing real file (backup lands where `BACKUP_ROOT` says),
   committed-mode untouched, absence-driven no-op. `mypy --strict` clean
   (`nix run nixpkgs#mypy -- --strict scripts/ct.py` works here).
4. Absorb the live contents into the repo IN THIS PR (repo-only, safe):
   `projects/agda-algebras/mcp.json` from aa master's fixed file; do NOT absorb
   from air main's current file; we will not carry `projects/agda-algebras/mcp.json`
   here.  Show William the diffs against every other copy.  Scan the contents for
   anything secret-looking before committing (they should be command paths and args
   only) — this repo may go public (issue #4); flag anything doubtful there too.
5. Docs in the same PR: `docs/architecture.md` (managed-member table + the
   new verified rule), `docs/worktree-workflow.md` (new-worktree ritual),
   and `docs/migration.md` if its residual-items list mentions `.mcp.json`.
6. Do NOT touch the live parents or checkouts from this worktree. Instead
   write the post-merge runbook into the PR description — from `main`, per
   project: `make install PROJECT=<p> DRY_RUN=1` → review → `make install
   PROJECT=<p> FORCE=1` → `scripts/link-worktrees.sh <p>` → `make check` →
   `claude mcp list` from a linked worktree to confirm live resolution.
   William runs it (or explicitly tells you to).

## Gates and open questions (ask, don't assume)

- Any live mutation (installs, force swaps, edits inside aa/air checkouts)
  is gated on William's explicit yes, after a dry run he can read.
- aa's three old worktrees (461/502/520) also still carry tracked
  `.claude` (known residual; `check` warns). Decide WITH William whether
  their stale `.mcp.json` copies get linked now or die with those
  branches.
- Should `add-project` scaffold anything for `.mcp.json`? (Presence-driven
  argues no; at most a mention in its "next steps" output.) Recommend one.

## Working style

Small commits with clear messages, following the global authorship and
attribution standing order in your loaded CLAUDE.md (no AI author or
Co-Authored-By; nontrivial commits end the body with
`AI-assisted development: <model> (Anthropic)`). For design forks, present
options with a recommendation and let William choose. End your final
message with the post-merge runbook and the absorption diffs he must
review.
