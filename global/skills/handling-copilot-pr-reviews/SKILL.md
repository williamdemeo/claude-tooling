---
name: handling-copilot-pr-reviews
description: Read, triage, and reply to a GitHub Copilot code review on a pull request — including the suppressed findings that never appear as inline comments and are invisible to the obvious API call. Use whenever asked to wait for, assess, address, or respond to PR review comments, or when a Copilot review needs requesting or re-requesting after pushing a fix.
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

## Requesting a review, and re-requesting after a fix

Copilot does **not** re-review when you push.  Each round must be requested:

```sh
gh api -X POST "repos/$OWNER_REPO/pulls/$PR/requested_reviewers" \
  -f "reviewers[]=copilot-pull-request-reviewer[bot]"
```

It returns the PR object with `requested_reviewers: []` — that is normal for the
bot, not a failure.  A review typically lands within ~15 minutes.  Rounds tend to
find progressively less; stop when one comes back with no comments *and* no
suppressed block, and say so rather than looping indefinitely.

## Triage: verify before agreeing or disagreeing

A finding is a hypothesis about the code, not a verdict.  Run something.

+  Reproduce the claimed behaviour through the real entry point, not by reading.
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
  -f body="$(cat reply.md)" --jq '.html_url'

# Suppressed findings have no thread — reply at PR level, quoting the finding.
gh api -X POST "repos/$OWNER_REPO/issues/$PR/comments" \
  -f body="$(cat reply.md)" --jq '.html_url'
```

Write the reply from a file, not an inline `-f body="…"` string: multi-line
markdown with backticks and quotes does not survive shell quoting reliably.

A reply that disagrees should quote the claim, state what was run, and paste the
output.  A reply that agrees should say what changed, and whether the defect was
wider than reported.

## Editing the PR body on a repo with classic Projects

`gh pr edit` fails on repositories that still have Projects (classic) enabled:

```
GraphQL: Projects (classic) is being deprecated … (repository.pullRequest.projectCards)
```

The mutation does not apply — verify rather than assume.  Use the REST endpoint:

```sh
python3 -c "import json,pathlib; print(json.dumps({'body': pathlib.Path('body.md').read_text()}))" > body.json
gh api -X PATCH "repos/$OWNER_REPO/pulls/$PR" --input body.json --jq .number
```

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

## Before claiming a fix works end to end

`cabal list-bin` (and its equivalents) hand back a **stale** binary if you built
only the test suite.  Build the executable explicitly before driving it, or an
end-to-end check will faithfully demonstrate the old behaviour.
