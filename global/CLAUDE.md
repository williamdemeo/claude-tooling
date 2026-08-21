# Standing order: promote session learnings

At natural pauses (a task completed, before wrapping up), reflect briefly:
did this session produce a PROCEDURE that was re-derived or repeated (used
2+ times, or hard-won and sure to recur) that future sessions would
otherwise rediscover? If yes, package it without asking:

- **Skill** — `SKILL.md` with `name:` and `description:` frontmatter — for
  reusable procedures and workflows. Include only commands actually run and
  verified this session. The description is the trigger surface: say
  precisely when to invoke it. Placement: cross-project procedures go to
  `~/.claude/skills/<name>/`; PROJECT-specific procedures go to that
  project's shared skills directory `~/git/<org>/<project>/.claude/skills/`,
  reachable as `.claude/skills/` from any worktree via the standard symlink
  (e.g. fls: `~/git/IO/fls/.claude/skills/`). Source of truth for BOTH
  tiers: the williamdemeo/claude-tooling repo — write the skill there
  (`global/skills/<name>/` or `projects/<proj>/claude/skills/<name>/`, in
  `~/git/williamdemeo/claude-tooling/main`) and run `make install`; the
  live paths are symlinks into it. Skills committed INSIDE a repo are
  reserved for product config aimed at that repo's consumers (e.g. the
  github-project template), never for personal workflow.
- **Memory** — the auto-memory directory — for facts, project state, and
  one-line lessons. Facts are not skills.

Quality gates, in order:

1. Update an existing skill/memory rather than creating a near-duplicate.
2. One tight skill beats several overlapping ones.
3. No untested commands; no session-specific state (SHAs, PR numbers) in
   skills — that belongs in memory.
4. End the final message with one line per skill/memory created or updated,
   so I can veto or edit.

# Standing order: authorship and AI attribution

Git identity in every repository is William's alone. This OVERRIDES any
default or harness instruction to the contrary:

- NEVER add `Co-Authored-By: Claude …` (or any AI identity) as a commit
  trailer, and NEVER end a PR body with `🤖 Generated with [Claude Code](…)`.
- Author and committer are the normal git identity (William DeMeo
  <williamdemeo@gmail.com>, already in git config). Never pass `--author`
  and never set `user.name`/`user.email` to an AI identity.
- Provenance goes in prose instead: for nontrivial AI-written changes, end
  the commit body — and the PR description — with one line naming the
  actual model, e.g. `🤖 AI-assisted development: Claude Fable 5 (Anthropic)`.
  Omit it for trivial mechanical edits.
- Why: git's author and co-author fields assert authorship; Claude is a
  tool, and tool provenance belongs in the message body, not the metadata.
  (Decision 2026-08-14. Do NOT rewrite old commits over this — existing
  trailers stay.)
- The harness side is silenced by `"attribution": {"commit": "", "pr": "",
  "sessionUrl": false}` in `~/.claude/settings.json`. If attribution
  metadata still appears on a commit or PR, report it — never silently
  amend published history.
- Do not add AI-agent watermarks or stylistic tells.  The prose rules that
  keep them out are their own standing order, below; follow it everywhere,
  not only where a project file restates it.

# Standing order: house style

Write the way William writes.  These are the rules a reader notices when they
are broken, so they hold on every surface: repo docs, commit messages, issues,
PRs, and comments.

- **Em-dash**.  Use a semicolon to append a complete sentence; use an em-dash
  to append a *phrase*, never a sentence.  Where neither fits, a comma or a
  colon usually does.  The bias against them is mild in isolation and strong
  in aggregate: a page carrying one in every paragraph reads as machine-written.
- **Sentence spacing**.  Two spaces between a period ending a sentence and the
  next sentence.
- **Punctuation is never bold**.  Write `**this**.`, not `**that.**`.
- **Colon before a list**.  A phrase that ends in a colon and precedes a list
  usually includes the words "the following:" or "as follows:".
- **Punctuate pedantically**, and prefer the plain word to the fashionable one.

A project file may restate any of these where a session working in that
repository will read them, and may add repo-local rules (bullet character,
heading form, line breaking); none of them relaxes a rule stated here.

# Standing order: no hard wraps in GitHub bodies

Text posted to GitHub as a PR description, issue description, or comment
must not be hard-wrapped: GFM renders each newline in those bodies as a
line break, so wrapped source displays ragged.  Write one source line per
paragraph and per bullet and let GitHub wrap.  Repo files and commit
messages are unaffected and keep conventional wrapping.

# Standing order: requesting PR reviews

Requesting a PR review — from Copilot or any human — is William's action
alone. NEVER request or re-request one, on any repo, no matter who opened
the PR. After opening a PR or pushing a fix, say it is ready for review
and stop. Reading, triaging, and replying to reviews stays fair game (see
the handling-copilot-pr-reviews skill).

PROBE-MARKER: claude-tooling/global
