---
name: handling-copilot-pr-reviews
description: Read, triage, and reply to a GitHub Copilot code review on a pull request — including the suppressed findings that never appear as inline comments and are invisible to the obvious API call. Use whenever asked to wait for, assess, address, or respond to PR review comments. Requesting (and re-requesting) a review is WILLIAM'S action alone — never request one; the request command is recorded here only for him to paste.
---

# Handling a Copilot review on a PR

Copilot's review is spread across three places with three different shapes, and
the obvious API call sees only one of them.  Reading it wrong means silently
missing findings.

## Fetch all three surfaces

```sh
OWNER_REPO=owner/repo
PR=95

# 1. Reviews — the summary body, and the SUPPRESSED findings (see below).
gh api "repos/$OWNER_REPO/pulls/$PR/reviews" \
  --jq '.[] | "── \(.user.login) [\(.state)] \(.submitted_at)\n\(.body)\n"'

# 2. Inline comments — anchored to a file and line.
gh api "repos/$OWNER_REPO/pulls/$PR/comments" \
  --jq '.[] | "── \(.path):\(.line // .original_line) \(.user.login)\n\(.body)\n"'

# 3. PR-level conversation.
gh api "repos/$OWNER_REPO/issues/$PR/comments" --jq '.[] | "\(.user.login): \(.body)"'
```

**The trap: suppressed comments.**  Copilot routinely puts findings in a
collapsed `<details><summary>Suppressed comments (N)</summary>` block inside the
*review body* — they are **not** in `pulls/*/comments` at all.  A review whose
overview says "generated no new comments" can still carry two real defects this
way.  Always read the review body in full; never conclude "no findings" from an
empty comments list.

**The other trap: the author login differs by surface.**  Reviews come from
`copilot-pull-request-reviewer[bot]`; inline comments come from `Copilot`.  A
filter written for one silently matches nothing on the other:

```sh
# reviews
--jq '[.[] | select(.user.login|test("copilot";"i"))] | length'
# inline comments
--jq '[.[] | select(.user.login=="Copilot")] | length'
```

## Requesting a review — William only, never a session

Requesting (and re-requesting) a Copilot review is WILLIAM'S action, never a
session's — creating or updating a PR does not entitle you to summon a
reviewer.  After pushing a fix, say the PR is ready for another round and
STOP.  The command below is recorded only so William can paste it (Copilot
does **not** re-review on push; every round needs an explicit request):

```sh
gh api -X POST "repos/$OWNER_REPO/pulls/$PR/requested_reviewers" \
  -f "reviewers[]=copilot-pull-request-reviewer[bot]"
```

It returns the PR object with `requested_reviewers: []` — that is normal for the
bot, not a failure.

**Review effort level cannot be set programmatically.**  Copilot code review has
two effort levels (GA 2026-08): Lite, the default, and Balanced (deeper analysis,
higher-reasoning model).  The level is chosen per request only in the web UI's
Reviewers section, or as an org/repo default for *automatic* reviews; the REST
request above, GraphQL, and `gh` expose no parameter for it.  If asked to request
a review at a specific depth, say the API cannot express it and leave the request
to William.  A review typically lands within ~15 minutes.  Rounds tend to
find progressively less; when one comes back with no comments *and* no
suppressed block, say so rather than suggesting another round.

## Triage: verify before agreeing or disagreeing

A finding is a hypothesis about the code, not a verdict.  Run something.

+  Reproduce the claimed behaviour through the real entry point, not by reading.
+  Then run a **control** that isolates the claimed cause, or the reproduction
   proves less than it looks.  A finding said a decoy import *inside a hole*
   broke a call; the same file with innocuous multiline hole text still worked,
   which is what established the decoy — rather than the multiline hole — as the
   cause.  Where the claim is about a tool's *output* being rejected downstream,
   feed that output to the downstream tool directly (writing the patched file and
   running the compiler on it turned "this can break" into `[ParseError]` at a
   named line).
+  Ask whether the defect is a **regression or pre-existing**, because it changes
   what the fix commit should claim.  Cheapest way, no rebuild: reimplement the
   old expression in a repl (`cabal repl lib:foo`, `node -e`, …) and run it over
   the reproduction.  Three findings in one review cycle all turned out to
   predate the branch that way.
+  When a fix is *suggested*, check the suggestion is right for the system —
   upstream tools have opinions.  A remedy that sounds safer can introduce a
   different wrong answer.
+  Check whether the finding is narrower or **wider** than stated: one reported
   site is often one of several instances of the same defect.
+  Check whether the stated *effect* is real even when the *mechanism* is.  A
   claim like "this aborts before the fallback" is worth testing; the abort may
   already happen earlier for an unrelated, pre-existing reason.

Fix at the root rather than patching the reported instance when the defect has a
single cause and several symptoms.  When you deviate from a suggestion, say so
and show the evidence.

## Replying

Reply to **every** comment, whether you accepted or rejected it.

```sh
# Reply on an inline comment's thread (needs the comment id).
gh api -X POST "repos/$OWNER_REPO/pulls/$PR/comments/$COMMENT_ID/replies" \
  -F body=@reply.md --jq '.html_url'

# Suppressed findings have no thread — reply at PR level, quoting the finding.
gh api -X POST "repos/$OWNER_REPO/issues/$PR/comments" \
  -F body=@reply.md --jq '.html_url'
```

Write the reply from a file and pass it as `-F body=@reply.md`, never as an
inline `-f body="…"` string and not even as `-f body="$(cat reply.md)"`: the
`@` form keeps multi-line markdown out of argv entirely, so nothing depends on
shell quoting or on the body fitting in `ARG_MAX`.

A reply that disagrees should quote the claim, state what was run, and paste the
output.  A reply that agrees should say what changed, and whether the defect was
wider than reported.

Two things worth stating explicitly when they are true, because they are what a
reviewer cannot verify alone: that the finding **predates the branch** (with how
you established it), and that you **deviated from the suggested remedy** and why.
A remedy aimed at the reported instance often leaves a sibling case broken — one
suggested blanking non-code *inside* a token while keeping the token; blanking the
whole token was both simpler and strictly wider, and the reply said so with the
case the narrower fix would have missed.

## Editing the PR body on a repo with classic Projects

`gh pr edit` fails on repositories that still have Projects (classic) enabled:

```
GraphQL: Projects (classic) is being deprecated … (repository.pullRequest.projectCards)
```

The mutation does not apply — verify rather than assume.  Use the REST endpoint,
with `-F key=@file` so the markdown never passes through argv:

```sh
gh api -X PATCH "repos/$OWNER_REPO/pulls/$PR" -F body=@body.md --jq .number
```

No temp JSON is needed; `@` makes `gh` read the value from the file.

The same deprecation breaks `gh issue view` / `gh pr view` without `--json`; pass
explicit fields (`gh issue view N --json number,title,body`) or use `gh api`.

## Watching for a review without polling by hand

Use a background monitor whose baseline counts **only** the reviewer's items, or
it will fire on your own replies:

```sh
for i in $(seq 1 60); do
  r=$(gh api "repos/$OWNER_REPO/pulls/$PR/reviews?per_page=100" \
        --jq '[.[] | select(.user.login|test("copilot";"i"))] | length' 2>/dev/null || echo 0)
  [ "$r" -gt "$BASELINE" ] && { echo "NEW COPILOT REVIEW ($r)"; break; }
  sleep 45
done
```

A requested review also shows up as a workflow run named `Running Copilot Code
Review`, which is usually the *newest* run for that commit — so a CI poll written
as `gh run list --limit 1` reports the review workflow's status, not the build's.
Filter by workflow name (`select(.name=="CI Pipeline")`) when waiting on CI after
pushing a review fix.  Its absence on a later push is also how you tell a
requested review from an automatic one.

## Before claiming a fix works end to end

`cabal list-bin` (and its equivalents) hand back a **stale** binary if you built
only the test suite.  Build the executable explicitly before driving it, or an
end-to-end check will faithfully demonstrate the old behaviour.
