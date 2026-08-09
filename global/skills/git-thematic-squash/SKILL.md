---
name: git-thematic-squash
description: Squash and reorder a long, messy PR branch into a handful of clean thematic commits WITHOUT interactive rebase (unavailable in this environment) — rebuild the history from the merge-base by staging file groups from the old head, verify the final tree is byte-identical, then force-push with lease. Use when asked to clean up or reorganize a branch's commit history.
---

# Reshape branch history without `git rebase -i`

Chronological squashing preserves rename/move churn (files added at one path,
moved later). When only the final tree matters, REBUILD instead: each commit
introduces its files once, at their final path, in their final form — renames,
reverts, and fix-up commits vanish from the story.

1. Preconditions: clean worktree; local == origin (`git fetch` + compare);
   linear history (`git log --merges BASE..HEAD` empty).
2. `BASE=$(git merge-base origin/master HEAD)`; `OLD=$(git rev-parse HEAD)`.
3. Enumerate the NET diff (`git diff --stat $BASE..HEAD`) and partition every
   file into 5–10 thematic chunks. Order them so each intermediate tree is
   coherent: a generator lands with its generated output; CI config lands
   after the script it runs; docs can forward-reference.
4. Build on a temp branch:

       git checkout -B tmp $BASE
       git checkout $OLD -- <chunk paths…> && git commit -m "…"   # per chunk

   Write each message to describe the FINISHED design (mine the old commit
   messages for material); keep Co-Authored-By trailers where they applied.
5. VERIFY — non-negotiable: `git diff tmp $OLD --stat` must be EMPTY
   (byte-identical tree ⇒ content provably unchanged, CI-green state carries
   over).
6. `git checkout <branch> && git reset --hard tmp && git branch -D tmp`
7. Run the project's pre-push gates, then `git push --force-with-lease`.
8. Confirm: `gh pr view N --json commits,mergeable`.

Tell the user the side effects: inline review threads on old commits show as
"outdated" (their text survives); CI re-runs from scratch on the new head.
