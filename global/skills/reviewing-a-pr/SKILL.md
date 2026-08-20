---
name: reviewing-a-pr
description: Review a pull request with two distinct instruments — an execution review (verify the PR's claims by building, testing, and driving the real shipped entry point) and a paths review (full line coverage of the new code, hunting the failure modes execution never drives) — and withhold any approve verdict until BOTH have run.  Use whenever asked to review, evaluate, or re-review a PR or large diff, especially one you helped design or specify; also after a bot review lands, to find what the bot missed.  Complements handling-copilot-pr-reviews, which covers triaging and replying to a bot's findings.
---

# Reviewing a PR: two instruments, one verdict

Learned the hard way: an execution-only review returned "approve, none blocking" on a large PR in which a bot review then surfaced eight genuine defects.  Every one lived in a corner the execution never drove — async-exception interleavings, cleanup on rare paths, a budget seam, a promise-vs-branch mismatch.  Execution proves that good behavior is present; it cannot establish that bad behavior is absent where nothing was executed.  Static path reading finds those corners but cannot confirm measured claims.  A trustworthy review is both, and the verdict must say which parts have run.

## The verdict rule

+  Do not write "approve" or "none blocking" until both instruments have run.  If only one has, scope the verdict in the review text itself: "claims verified by execution; adversarial path coverage incomplete; verdict withheld on the lifecycle corners."
+  State the coverage basis inside the verdict — "100% of the two new modules read; suite reproduced; nine live probes" — so the reader can see what the verdict rests on.
+  Self-review bias is real: if you authored the design brief the PR implements, conformance-checking crowds out adversarial reading, and it feels thorough because the claims all verify.  The paths pass is the mitigation; execution alone is not.

## Instrument 1 — the execution review (claims)

+  Stand up a detached, disposable worktree at the PR head and build in the background while you read: `git worktree add ../review-N origin/<head-branch>`.
+  Check the base before anything else: `git merge-base --is-ancestor origin/main HEAD` tells you whether the branch sits on current main; `git diff --stat origin/main...HEAD` scopes the diff.
+  Run the full test suite yourself; never take the PR body's pass counts on faith.
+  Drive the REAL shipped entry point — the stdio transport, the CLI, the HTTP surface — not just the handlers the tests call.  Unit tests assert handler values; they do not show what a client actually receives.
+  Reproduce measured claims (latencies, counts, sizes) and quote your own numbers next to the PR's.
+  Reviewer-error rule: when your probe shows a null or a missing field, suspect your own extraction before filing a finding — read the full response body first.  A field-name mismatch in the reviewer's one-liner looks exactly like a bug in the PR.

## Instrument 2 — the paths review (corners)

Read 100% of the new and changed lines, and read them for failure, not for conformance to the design.  The hunt list — every entry found in the wild at least once:

+  `catch SomeException` sitting inside or beside a `timeout`, or anywhere a `killThread` can land: it swallows the asynchronous exception and converts a timeout or cancellation into a misreported crash, or keeps a "stopped" thread alive.
+  Unmasked take/put windows on shared slots (MVar and kin): an async exception between the take and the put leaks the slot empty, and every later user blocks forever.
+  A shutdown/closed latch checked under lock A guarding nothing acquired later under lock B: a full shutdown can run between the two acquisitions, and the request then creates the very resource shutdown existed to prevent.  Re-check the latch under the lock that guards the acquisition; found in the wild after three bot rounds and three author rounds missed it.
+  Cleanup that runs only on the happy exit: shutdown on EOF but not on the exception path (missing `finally`); a dead resource replaced without closing the old one (leaked handles per respawn).
+  Budget seams: two full timeouts stacked across a spawn-then-request boundary, so the documented per-request bound silently doubles.
+  Unbounded writes: the read side has a deadline, the send side can block forever on a full pipe.
+  Promise-versus-branch: the description or docstring promises X "for every case"; one branch returns less.  Check every branch against the contract text, not against the happy path.
+  Duplicated canonical form: the PR packages a concept into a reusable unit but leaves older inline copies unretrofitted — now the concept exists twice or three times.
+  Taxonomy leaks: a shared fallback constructor hardcodes one label (a stage, a category) and is reached from contexts where the label is wrong.
+  Untested branches: for each new branch, grep the tests for something that drives it.  A branch no test reaches is a finding by itself — and sometimes the deeper finding is that no INPUT reaches it either, which changes what the fix should be.

Form hypotheses while reading and settle them by probing the built artifact, not by more reading.  A ten-minute live probe routinely reclassifies a finding's severity in either direction.

## When a bot review lands on the same PR

+  Triage its findings per the handling-copilot-pr-reviews skill: verify each against the code, then classify — accept; accept the defect but override the remedy (with evidence); or reword-not-code when the defect is in the prose.
+  Check each finding for being narrower or wider than stated; the bot often reports one instance of a two-instance defect.
+  Then run the paths pass anyway over whatever you had not yet covered.  The test of a second review is finding things the bot ALSO missed; if you only triage, you have added process, not assurance.

## Commands (verified)

```sh
gh pr view N --json title,body,baseRefName,headRefName,additions,deletions,changedFiles
gh pr diff N --name-only
git worktree add ../review-N origin/<head-branch>     # detached, disposable
git merge-base --is-ancestor origin/main HEAD && echo "based on current main"
git diff --stat origin/main...HEAD
git show "origin/<head-branch>:path/to/file"          # read a file without the worktree
git worktree remove --force ../review-N               # afterwards
```

Build and test inside the project's pinned toolchain, and run long suites in the background while reading the diff.

## Writing it up

+  Rank findings by leverage, not by file order; give each a site, the mechanism, and a concrete fix shape.
+  Where you override a suggested remedy (a bot's or the author's), say so and show the evidence — the disagreement is part of the deliverable.
+  End with the verdict, its coverage basis, and what was deliberately left to follow-ups versus what gates the merge.
