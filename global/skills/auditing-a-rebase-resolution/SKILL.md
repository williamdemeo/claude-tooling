---
name: auditing-a-rebase-resolution
description: Audit a branch after someone rebased it onto a rewritten target and resolved conflicts by hand, to find edits the resolution introduced by accident (stray files, residue copies of target commits) without reverting changes that were intentional. Use when asked to "clean up" a rebased branch, when a PR's diff shows files it should not touch, or before re-rebasing a stacked branch; also covers the rescue-ref and lease-guarded push pattern for rewriting a pushed branch without the stash.
---

# Auditing a hand-resolved rebase

A rebase that stopped on conflicts is resolved by a human, and the resolution can carry
accidents: a hunk taken from the wrong side, a file the branch should not touch, or a
residue copy of a commit the target already has.  The audit reconstructs what a purely
mechanical replay would have produced and diffs the actual result against it, so only
the human's decisions remain to be judged.

## 1. Locate the pre-rebase tip and the two bases

The branch reflog records the rebase and the tip before it:

```
git -C <worktree> reflog show --date=short <branch> | head -12
```

Read off `<old-tip>` (the last commit before the `rebase (finish)` entry) and
`<old-base>` (the `branch: Created from …` entry, or `git merge-base <old-tip> <old-target>`).
`<new-base>` is the target's tip the branch was rebased onto (`git merge-base HEAD <target>`).

## 2. Reconstruct the mechanical replay and diff against it

`merge-tree` performs the three-way merge in memory and prints a tree id, without
touching the worktree; a non-zero exit lists the files it could not merge:

```
git -C <worktree> merge-tree --write-tree --merge-base=<old-base> <old-tip> <new-base>
git -C <worktree> diff --stat <expected-tree> <actual-tip>
git -C <worktree> diff <expected-tree> <actual-tip>
```

Every file in that diff is one the human changed beyond the mechanical merge.  Files
that `merge-tree` reported as conflicts are where a manual decision was unavoidable;
read those hunks and judge them (the expected tree carries conflict markers there, so
the diff shows the markers being removed and one side kept).  Any other file in the
diff is an accident until proven otherwise.

## 3. Find residue copies of target commits

A commit whose content the target already has normally drops out of a rebase, but a
conflict resolution can leave it behind with a small residual diff:

```
git -C <worktree> cherry -v <target> HEAD        # "-" marks patches already upstream
git -C <worktree> show --stat <suspect>          # a residue touches only the files the resolution changed
git -C <worktree> log --format='%h %s' <target> -8   # look for the same title on the target
```

Drop a residue by replaying only the commits after it:
`git rebase --onto <target> <residue> <branch>`.

## 3b. The conflict git cannot show you: a guard the other branch added

A clean textual merge is not a clean semantic one, and the dangerous case is
the one where neither side touched the same lines.  If the branch you rebase
onto added a *precondition* somewhere general, your feature can end up outside
it and stop working while every test that runs still passes.

Seen 2026-09-12 on williamdemeo/website: main added an `--outbound` mode to a
checker and, reasonably, stopped loading the redirect map unless it was
needed, `if args.map or args.assets:`.  The rebased branch's `--edge` mode
needed that map, for one narrow purpose: to know which built pages are
redirect stubs so it could skip them.  Run alone it got an empty rule list,
skipped nothing, followed 112 redirects and compared each target's HTML
against a stub's.  112 failures that said nothing, and `nix flake check` was
green throughout, because that check needs the network and is not a flake
check.

So, after the rebase resolves and the build passes:

+  **Run the checks that are NOT in the build gate.**  Integration checks,
   network checks, anything a sandbox cannot run: those are exactly where a
   semantic break hides, because nothing else exercises them.
+  **Compare a count against the last known-good run**, not against zero.  The
   number to be suspicious of is one that moved: "56 checked" became "168
   checked", and the failures were incidental to that.
+  **When a count is wrong, instrument rather than reason.**  Monkeypatching
   the function to print what it selected, and calling the same function
   directly with the same arguments, localized this in two runs: 56 from a
   direct call and 168 through `main()` says the difference is in the caller,
   not in the callee.
+  `grep` the other branch's diff for new `if` guards around shared setup:
   `git diff <merge-base> <target> -- <file> | grep -n '^+.*if '`.

## 4. Rewrite safely: rescue ref, verification, lease

Pin the tip before rewriting and never use the stash (shared across worktrees):

```
git -C <worktree> update-ref refs/wip/<branch>-before-fix <tip>
```

After the rewrite, verify content rather than trusting the log: the intended commit's
patch should be unchanged modulo hunk headers,

```
diff <(git show <old-commit> --format='' | grep -v '^index \|^@@') \
     <(git show <new-commit> --format='' | grep -v '^index \|^@@') && echo identical
```

and files that must equal the target's should diff empty
(`git diff <target> HEAD -- <files> | wc -l`).  Run the project's gates, then push with
the lease set to the tip the remote is known to hold, and drop the rescue ref:

```
git -C <worktree> push --force-with-lease=<branch>:<remote-tip> origin <branch>
git -C <worktree> update-ref -d refs/wip/<branch>-before-fix
```

In a stack of PRs, rewriting a lower branch obliges a re-rebase of every branch above
it (`git rebase --onto <new-lower-tip> <old-lower-tip> <upper-branch>`), each with its
own lease.
