# Standing orders

Both orders live in `global/CLAUDE.md` (deployed to `~/.claude/CLAUDE.md`),
so every session carries them.

## 1. Promote session learnings

**Summary**.  At natural pauses, a session that re-derived or repeated a PROCEDURE
(used 2+ times, or hard-won and sure to recur) packages it — without asking — as a
**skill**; facts, project state, and one-line lessons go to **memory** (the
auto-memory directory).  The final message lists every skill/memory created or
updated, so William can veto or edit.

### Where new skills go (the placement principle applied)

+  **Cross-project procedure** → `global/skills/<name>/` in this repo, then
   `make install` (deploys the `~/.claude/skills/<name>` symlink).
+  **Project-specific procedure** → `projects/<proj>/claude/skills/<name>/`
   in this repo, then `make install PROJECT=<proj>`.
+  **Product config** (teaching a repo's consumers) → committed in that repo
   (e.g. github-project's template skills); never William's personal workflow.

A session may also drop a scratch skill directly into a live `~/.claude/skills/` or
`<parent>/.claude/skills/` dir (they stay real dirs precisely so unmanaged skills
work); promotion into this repo is what makes it durable and recoverable.

### Quality gates (now partially machine-enforced)

**The order's gates, and what `make check` does about them**.

1.  *Update an existing skill rather than near-duplicating*: `make list` shows the
    inventory; the lint fails on duplicate names within any one session's visible set
    (global + one project).
2.  *One tight skill beats several overlapping ones*: human judgment.
3.  *No untested commands; no session junk*: the lint FAILS on bare commit SHAs and
    PR/issue numbers in skill bodies, and on absolute paths that no longer exist
    (stale-path lint).  A line containing `lint-skills: ok` is exempt when a hex
    string or number is legitimately part of a procedure.
4.  *Frontmatter discipline*: the lint fails on missing/mismatched `name:`
    (must equal the directory name) and empty `description:`; it warns when a
    description doesn't say when to trigger.

## 2. Authorship and AI attribution (2026-08-14)

Summary: commits and PRs never carry an AI identity as author, committer, or
`Co-Authored-By`; the git identity is William's, and AI provenance is recorded — when
the assistance was nontrivial — as a plain commit-body / PR-description line.
+ Commit-body line: `AI-assisted: <model> (Anthropic)`;
+ PR-body line: `🤖 AI-assisted development: <model> (Anthropic)`.
Existing history keeps its old trailers; nothing is rewritten.

Enforcement is layered:

+  **Instruction layer**: the order in `global/CLAUDE.md` (overrides the harness's
   default commit/PR instructions).  `projects/fls/CLAUDE.md` restates it for fls,
   replacing that project's old trailer convention.
+  **Harness layer**: `~/.claude/settings.json` carries
   `"attribution": {"commit": "", "pr": "", "sessionUrl": false}` — the supported
   Claude Code setting (empty text hides the commit/PR attribution; `sessionUrl: false`
   drops the `Claude-Session:` trailer on web/Remote Control commits).
   `settings.json` is managed by this repo: `global/settings.json` deploys as the
   `~/.claude/settings.json` symlink via `make install`, so the attribution block
   recovers with everything else.  Editing the live file edits the repo working tree
   — commit it, same as CLAUDE.md and skills.
+  **Web containers**: the fls setup script
   (`projects/fls/web-environment/setup-script.sh`, step 5) sets William's git
   identity and writes the same attribution block into the container's
   `~/.claude/settings.json`, even in toolchain-only setups.
