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

PROBE-MARKER: claude-tooling/global
