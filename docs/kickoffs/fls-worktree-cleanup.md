<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-3-fls-worktree-cleanup.md
     (deployed 2026-08-09, William's approval). Launch a fresh session with:
     Read and execute `~/claude-kickoff-prompts/kickoff-3-fls-worktree-cleanup.md` -->

# Kick-off: clean up the fls worktree forest

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt. William makes every destructive
decision; your job is inventory, classification, and a plan he can approve
in batches. Push back where anything seems misguided — he wants that.

## Where you are

fls = formal-ledger-specifications, IOG professional work. Main checkout
(`master` branch) at `~/git/IO/fls/master` — the only place for fetch/pull
and worktree bookkeeping. Worktrees are scattered over many container dirs
(`worktrees/`, `worktrees/william/`, `worktrees/carlos/`,
`worktrees/claude/`, `worktrees/fd/`, `william/`, `carlos/`, `copilot/`, …)
— trust only `git worktree list --porcelain`, never directory listings.

Claude config: `~/git/IO/fls/CLAUDE.md` and `~/git/IO/fls/.claude/` are
managed by `~/git/williamdemeo/claude-tooling/main` (possibly still
pre-migration — check). Worktree roots carry `.claude` symlinks; the
`/.claude` exclude line lives in master's `.git/info/exclude`.

## Snapshot (2026-08-09 — re-measure, don't trust)

- 105 worktrees (incl. master); 109 local branches, **73 of them tracking
  upstreams already deleted at origin** (as of the 2026-08-07 fetch).
- Branch-tip ages across worktrees: median ~123 days, p75 ~192, max ~288;
  only a handful touched in the last two weeks.
- 2 worktrees on detached HEAD (`carlos/bisimulation-expired-dreps`,
  `carlos/refactor-epoch`).
- 3 worktrees still contain TRACKED `.claude` config from old branches
  (`worktrees/claude/agda-skill-and-session-hook`,
  `…/gifted-bardeen-iiix4j`, `…/peaceful-carson-u3ojhc`).
- Some container dirs mix in non-git junk (`~/git/IO/fls/william/` holds
  ~1000 entries including photos). LIST such junk; never touch it.

## Mission

Reduce to roughly a dozen (or fewer) worktrees William actively works on,
without losing one byte of unmerged or uncommitted work. Disk reclaimed is
a nice side effect, not the goal; safety is the goal.

## Hard safety rules

1. Read-only until William approves a written plan. The first mutation of
   any kind (including `fetch --prune`) gets its own explicit yes.
2. Removal is always `git worktree remove` (never bare `rm -rf`), so git
   metadata stays consistent; finish with `git worktree prune` and a final
   `git worktree list` diff.
3. A worktree that is dirty, has stashes, or has commits not on any origin
   branch (`git cherry origin/<branch> HEAD`, `git rev-list @{u}..HEAD`,
   `git stash list`) is NEVER removed in a batch — each such case is a
   per-item decision with the evidence shown (offer: push a rescue branch,
   or leave it).
4. Before any `git branch -D`, record branch name + tip SHA in a rescue
   manifest file (`~/git/IO/fls/worktree-cleanup-<date>.md`) so everything
   is re-creatable; branch deletion is a SEPARATE approval from worktree
   removal.
5. Other people's dirs (`carlos/`, `facundo/`, `heinrich/`, `tferariu/`,
   `copilot/`, …) are IN SCOPE, but every non-worktree dir in `~/git/IO/fls/`
   (`master-old`, `master-new*`, `master-artifacts`, `legacy-latex`,
   `ARCHIVE`, …) is OUT OF SCOPE unless William explicitly widens scope —
   list them with sizes as an appendix so he can decide separately.

## Procedure

1. `git -C ~/git/IO/fls/master fetch --prune` (after its yes) so upstream
   state is current.
2. Inventory every worktree: path, branch (or detached), upstream status
   (gone / ahead / behind), dirty?, stash?, unpushed-commit count, last
   commit date, tracked-.claude?. One table, sorted worst-to-safest.
3. Classify: **KEEP** (recent activity, or William names it), **REMOVE**
   (clean, nothing unpushed, upstream gone or fully merged), **ASK**
   (dirty / unpushed / detached / stash / tracked-.claude / anything odd).
4. Present the plan: counts + full table + the ASK list with evidence.
   Get William's yes (he may promote/demote items).
5. Execute REMOVEs in batches of ~10 with running output; handle ASKs one
   by one; then `git worktree prune`; write the rescue manifest.
6. Afterwards: run claude-tooling's `make check PROJECT=fls` and
   `scripts/link-worktrees.sh fls`; report final worktree list, branches
   deleted (with recorded SHAs), disk reclaimed (`du -sh` before/after on
   container dirs), and anything left for William.

## Related follow-ups (mention at the end, don't do)

- agda-algebras has 127 worktrees and deserves the same treatment (94 of
  them still carry tracked `.claude`, which also blocks claude-tooling's
  stage-4 re-linking).
- williamdemeo.github.io: all ~23 worktree registrations broke when the
  repo moved out of `~/git/williamdemeo/MKDOCS/` — `git worktree repair`
  (or prune + re-add) from `williamdemeo.github.io/main`.
- The empty `~/git/williamdemeo/MKDOCS/` leftover dir.
