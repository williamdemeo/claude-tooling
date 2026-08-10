---
name: worktree-forest-cleanup
description: Safely reduce a repo's sprawling git-worktree forest (dozens–hundreds of worktrees) to just the active ones without losing any unmerged or uncommitted work. Use when asked to clean up, inventory, or prune worktrees/branches of a repo with many worktrees (fls, agda-algebras, …). Covers read-only inventory + classification, the safety model, batch removal with rescue branches/patches, and the manifest.
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

Script pitfalls (hit in practice): `grep -c` prints 0 AND exits 1, so
`x=$(... | grep -c '^+' || echo '?')` yields "0\n?" — corrupts TSVs; zsh does not
word-split unquoted `$LIST` in for-loops — iterate a file with `while read`;
bash variable names must be ASCII.

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
   as explicit per-worktree compound commands instead.)
4. `git worktree prune`; diff final `git worktree list` against plan; rmdir ONLY
   container dirs your removals emptied (a bare `find -type d -empty` also surfaces
   .git internals of unrelated clones — never touch those).
5. Append an execution log to the manifest: batches, rescue branches + SHAs,
   rescue artifacts, final list, du before/after.
