---
name: worktree-forest-cleanup
description: Safely reduce a repo's sprawling git-worktree forest (dozens–hundreds of worktrees) to just the active ones without losing any unmerged or uncommitted work. Use when asked to clean up, inventory, or prune worktrees/branches of a repo with many worktrees (fls, agda-algebras, williamdemeo.github.io, …), including a repo whose container directory itself moved on disk. Covers read-only inventory + classification, the safety model, repo-relocation repair, batch removal with rescue branches/patches, and the manifest.
---

# Worktree-forest cleanup

Two strictly separated phases: **read-only inventory → written plan → approval**,
then **execution in approved batches**. The user makes every destructive decision.

## Safety model (what actually risks data)

- Removing a CLEAN attached worktree never loses commits — the branch ref lives in
  the main repo and survives. Only `git branch -D` risks commits; keep branch
  deletion a SEPARATE later approval with a name+SHA manifest written first.
- `refs/stash` is shared repo-wide: stashes are NEVER at risk from worktree
  removal. `git stash list --format='%gd | %ci | %gs'` shows which branch each
  entry came from.
- Real risks: DETACHED HEADs whose commit no branch contains
  (`git branch --contains <sha>` and `-r --contains` both empty), uncommitted
  modifications, and untracked files.
- Never `git worktree remove --force` in a batch: plain remove refuses on
  dirty/untracked worktrees, which auto-escalates surprises to per-item decisions.
  Ignored/excluded files (e.g. excluded .claude symlinks) do NOT block removal.
- Removal is always `git worktree remove` (never bare rm -rf), finish with
  `git worktree prune` and verify the final `git worktree list` against the plan.

## Repo relocation (stale backpointers, not stale content)

If the repo's own container directory moved on disk (e.g. `~/git/<org>/OLD-NAME/…` →
`~/git/<org>/NEW-NAME/…`), `git worktree list --porcelain` shows most entries as
`prunable` with `gitdir file points to non-existent location` — but the worktree
directories themselves moved WITH the repo and are sitting intact under the NEW
path, just with a stale `.git` back-pointer file (`cat <dir>/.git` shows the OLD
path). **Do not prune.** Pruning here would discard repairable registrations for
checkouts whose content — including any uncommitted work — is fully intact; a
report of "work lost at move time" would be false.

Fix: from the NEW main checkout, find every on-disk worktree directory (`find
<worktrees-root> -mindepth 1 -maxdepth 2 -type d`, watching for one extra nesting
level under any `claude/`-style namespace subdirectory) and pass them all to one
`git worktree repair <dir> <dir> …`. This fixes the back-pointer in both
directions — the worktree's `.git` file and the main repo's own
`.git/worktrees/<name>/gitdir` record — even when the two sides predate the move
by different amounts (one worktree can point at an even older path structure than
the rest; repair handles each independently). Re-run `git worktree list
--porcelain` afterward and confirm `prunable`/`detached` counts are both zero
before starting the normal inventory below.

## Inventory (read-only)

Trust only `git worktree list --porcelain` (never directory listings — containers
mix in unregistered clones and junk). Per worktree collect: branch or DETACHED
(`symbolic-ref --quiet --short HEAD`), upstream + gone
(`rev-parse --abbrev-ref @{u}`; if it fails but `git config branch.<b>.merge`
exists ⇒ upstream GONE), ahead/behind (`rev-list --left-right --count @{u}...HEAD`),
dirty split into modified vs untracked (`status --porcelain`, count `^??` vs rest),
merged-ness (`merge-base --is-ancestor HEAD origin/master`, else
`git cherry origin/master HEAD | grep -c '^+'` — 0 ⇒ fully patch-equivalent,
e.g. rebase-then-merge), last commit date, tracked config files (`ls-files`).
Also: `gh pr list --state open --json number,headRefName` (open PR ⇒ KEEP),
local-only tags (`git tag` vs `git ls-remote --tags origin`), branches without
worktrees, and check `git config fetch.prune` + FETCH_HEAD mtime before assuming
a fetch --prune is needed at all.

Script pitfalls (hit in practice):
- `grep -c` prints 0 AND exits 1, so `x=$(... | grep -c '^+' || echo '?')`
  yields "0\n?" — corrupts TSVs.
- zsh does not word-split unquoted `$LIST` in for-loops — iterate a file with
  `while read`.
- bash variable names must be ASCII; in zsh specifically, never name a loop/local
  variable `path` — it aliases the shell's own `$PATH` array, so `path=$x`
  silently breaks every command lookup for the rest of that call (symptom:
  "command not found: git" for a git that worked one line earlier).
- `git rev-parse --abbrev-ref @{u}` ECHOES THE LITERAL ARGUMENT to stdout even on
  failure (git's rev-vs-path disambiguation design) — `upstream=$(git rev-parse
  --abbrev-ref '@{u}' 2>/dev/null)` on a branch with no upstream yields
  `upstream="@{u}"`, not empty, so `[ -z "$upstream" ]` silently never fires and
  the GONE/NONE fallback never runs. Check the exit status explicitly instead:
  `git rev-parse --abbrev-ref '@{u}' >"$tmp" 2>/dev/null; if [ $? -eq 0 ]; then
  upstream=$(cat "$tmp"); else upstream=""; fi`.

## Classify

KEEP = open PR / named by user / main checkout. ASK = detached, dirty, untracked,
or anything odd (each with evidence: files touched, unreachable-commit counts).
REMOVE = clean and attached — regardless of whether the branch is merged (the
branch stays; flag unmerged branches as excluded from any future deletion).
Present: counts + full table (a manifest .md file beats a terminal dump) + ASK
evidence. Non-worktree dirs in the same tree are OUT OF SCOPE: list with `du -sh`
as an appendix.

## Execute (after approval)

1. Clean REMOVEs in batches of ~10: `git -C <main> worktree remove <path>`,
   report OK/REFUSED per item.
2. Detached HEADs: `git branch rescue/<name> <sha>` BEFORE removal.
3. Dirty: rescue untracked (`git ls-files --others --exclude-standard`, `cp -p`
   preserving relative paths, `cmp -s` verify, then rm originals), save mods as
   `<name>@<baseSHA>.patch` via `git diff HEAD`, `test -s` the patch,
   `git apply --stat` to eyeball, then `git reset --hard HEAD` and remove.
   (Permission classifiers may block a monolithic rescue script — run the steps
   as explicit per-worktree compound commands instead; expect `git reset --hard`
   specifically to need its own explicit go-ahead even after the batch itself was
   approved, since it's flagged as destructive regardless of what's already
   rescued.) For untracked content already confirmed pure junk (tool-local
   config, caches — nothing worth a rescue copy), skip the cp/patch dance:
   `git clean -fdn` to preview, `git clean -fd` to clear it, then plain remove.
4. Watch for a directory whose checked-out branch doesn't match its own name —
   sign of a worktree that was reused for unrelated follow-up work after the
   original branch merged. Not itself risky (check both the original and the
   current branch's merge status same as any other), but confirm before folding
   it into a batch by name-pattern alone.
5. `git worktree prune`; diff final `git worktree list` against plan; rmdir ONLY
   container dirs your removals emptied (a bare `find -type d -empty` also surfaces
   .git internals of unrelated clones — never touch those).
6. Append an execution log to the manifest: batches, rescue branches + SHAs,
   rescue artifacts, final list, du before/after.
