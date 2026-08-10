<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-4-agda-algebras-and-website-worktree-cleanup.md
     Launch a fresh session with:
     Read and execute `~/claude-kickoff-prompts/kickoff-4-agda-algebras-and-website-worktree-cleanup.md` -->

# Kick-off: worktree cleanup for agda-algebras and williamdemeo.github.io

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt plus the user skill
**`worktree-forest-cleanup`** (~/.claude/skills/, also in claude-tooling
global/skills/) — invoke it first; it encodes the safety model and the exact
procedure, validated on the fls cleanup of 2026-08-09 (105 → 13 worktrees,
zero bytes lost; manifest: `~/git/IO/fls/worktree-cleanup-2026-08-09.md`).
William makes every destructive decision; your job is inventory,
classification, and a plan he approves in batches. Push back where anything
seems misguided — he wants that.

## Job 1 — agda-algebras (the big one)

- Main checkout: `~/git/ualib/agda-algebras/master` — **127 registered
  worktrees** as of 2026-08-09 (re-measure with `git worktree list
  --porcelain`; trust only that, never directory listings).
- This is William's personal repo (github.com/ualib/agda-algebras); default
  branch `master`. `gh pr list` for open PRs → KEEP set.
- ~94 worktrees carry TRACKED `.claude` config from old branches. In THIS
  repo that is the NORM (any checkout made after the config landed has it),
  not an anomaly — tracked `.claude` alone is NOT an ASK trigger here, or
  ~94 per-item decisions would swamp William. Classify on the usual
  evidence (dirty / unpushed / stash / detached / odd); removing clean ones
  is safe (branch refs keep everything) and actively unblocks
  claude-tooling's stage-4 re-linking for this project.
- Container dirs to expect (verify against porcelain): worktree containers
  under `~/git/ualib/` (e.g. `~/git/ualib/worktrees/`,
  `~/git/ualib/agda-algebras/worktrees/`) mixed with NON-git junk in
  `~/git/ualib/agda-algebras/` itself (PDFs, files.zip, `master-dirty/`, …).
  Non-worktree dirs are OUT OF SCOPE: list with sizes as an appendix.
  Related clones that are NOT this forest: `~/git/williamdemeo/agda-algebras`
  (+ two `-old-*` siblings), `~/git/ualib/agda-algebras-20250323` — appendix
  only.
- Check early (cheap, shapes the plan): FETCH_HEAD age + `git config
  fetch.prune`; `git stash list` (shared repo-wide); detached HEADs
  (`git branch --contains`/`-r --contains` on their SHAs); local-only tags.
- Rescue manifest: `~/git/ualib/agda-algebras/worktree-cleanup-<date>.md`.
- Afterwards: claude-tooling `make check PROJECT=agda-algebras` and
  `scripts/link-worktrees.sh agda-algebras` (from
  `~/git/williamdemeo/claude-tooling/main`).

## Job 2 — williamdemeo.github.io (small, mostly bookkeeping)

- Main checkout: `~/git/williamdemeo/williamdemeo.github.io/main`. The repo
  moved out of `~/git/williamdemeo/MKDOCS/…`, so its ~24 registrations still
  point at OLD MKDOCS paths (shown as **prunable**) — BUT the worktree dirs
  themselves MOVED WITH THE REPO and sit on disk under
  `williamdemeo.github.io/worktrees/` with stale `.git` back-pointers
  (verified 2026-08-09: e.g. `worktrees/13-m2-4-rescue-posts/.git` →
  `gitdir: …/MKDOCS/…`). Their contents — including any uncommitted work —
  are INTACT. **Do NOT prune first**; pruning would orphan repairable
  checkouts and a report of "work lost at move time" would be false.
- Plan: FIRST `git worktree repair <path>…` from the new main checkout,
  passing each on-disk dir under `worktrees/` (repair fixes registration and
  back-pointer both ways); re-inventory; only then `git worktree prune
  --verbose` for registrations whose dirs truly exist nowhere on disk; then
  classify keep/remove like any forest — dirty/unpushed checkouts are
  per-item ASK with evidence, and William names what he wants kept.
- Then: `make check PROJECT=williamdemeo.github.io` + link-worktrees from
  claude-tooling.
- Finally: the leftover `~/git/williamdemeo/MKDOCS/` dir is empty —
  ask William for the yes to rmdir it.

## Ground rules (same as fls; the skill has the details)

1. Read-only until William approves a written plan; the first mutation of any
   kind (including any fetch) gets its own explicit yes.
2. `git worktree remove` only, never `--force` in batches, never bare rm -rf
   on registered worktrees; finish with `git worktree prune` and a final list
   diffed against the plan.
3. Dirty / detached / stash-bearing / odd worktrees are per-item ASK
   decisions with evidence; rescue via branches (`rescue/<name>` at detached
   SHAs) and verified patches before any discard.
4. Branch deletion is a SEPARATE approval from worktree removal; record
   name + tip SHA in the manifest before any `git branch -D`; only propose
   branches provably merged (ancestor of origin/<default> or `git cherry`
   fully patch-equivalent).
5. Update the manifest as you go; report disk before/after per container.
