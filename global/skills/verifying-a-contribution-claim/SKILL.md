---
name: verifying-a-contribution-claim
description: Establish whether an "I contributed to X" claim is true before it is published, using gh and the GitHub search API, and distinguish merged upstream work from work merged into the author's own fork or own single-member organization. Use before writing any project list, CV entry, research statement, cover letter, or README line that names a repository the author does not own; and whenever a source (an issue, an older CV, a draft) hands you a list of upstream projects to cite. Covers proving a negative, the fork-and-own-org trap, attribution when the program is someone else's, and which GitHub URL renders the evidence to a signed-out reader.
---

# Verifying a contribution claim

A claim of "contributions to `agda-stdlib`" with nothing behind it is worse than
omitting the line, because the reader who checks is the reader you wrote it for.
Everything below was run on 2026-09-11 against `williamdemeo` while building the
secondary projects list for williamdemeo.org, where three of the six claims a
GitHub issue proposed turned out to be unsupported.

## The order to do it in

1.  **Count the merged work.**  `gh pr list` is authoritative and cheap:

        gh pr list --repo OWNER/REPO --author LOGIN --state merged --limit 50 \
          --json number,title,mergedAt,additions,deletions

    Read `additions`/`deletions`.  Six merged pull requests sounds substantial
    until they are three README revisions, and the honest line says which.

2.  **Prove the negative properly.**  Zero merged is not zero contribution: work
    can land as a commit without a pull request.  Three queries, all of which
    must be zero before you write "no contribution exists":

        gh pr list --repo OWNER/REPO --author LOGIN --state all --limit 50 --json number,state
        gh api -X GET search/commits -f q="repo:OWNER/REPO author:LOGIN" --jq .total_count
        gh api -X GET search/issues  -f q="repo:OWNER/REPO author:LOGIN type:issue" --jq .total_count

    A fork under the author's account proves nothing either way; a fork last
    pushed two years ago is a reading copy, and `gh repo view --json pushedAt`
    says so.

3.  **Find what is actually there**, rather than testing only the names the
    source handed you.  One query lists every repository outside the author's
    own namespace with merged work in it:

        for p in 1 2 3 4 5 6 7; do
          gh api -X GET search/issues \
            -f q="author:LOGIN type:pr is:merged -user:LOGIN" -f per_page=100 -f page=$p \
            --jq '.items[] | .repository_url | sub(".*/repos/";"")'
        done | sort | uniq -c | sort -rn

    That tally is the real record, and it is usually a different list from the
    remembered one.

## The fork-and-own-org trap

`-user:LOGIN` excludes the personal namespace and nothing else, so the tally
above still counts organizations the author created and forks the author owns.
Both look exactly like upstream contributions in every listing.  Two checks
settle it, and neither is optional:

    gh repo view OWNER/REPO --json nameWithOwner,isFork,parent,stargazerCount
    gh api orgs/OWNER/members --jq '[.[].login] | join(", ")'

Measured case: 31 merged pull requests adding Lean code to a book, 11 in one
organization and 20 in another.  Both repositories were forks of the same
upstream, and one organization had exactly one member, the author.  The five
pull requests to the real upstream were all **closed unmerged**.  The claim
does not survive, and `gh pr list --state all` on the parent is what shows it.

## Attribution, when the program is someone else's

Before writing "my project", read the landing page and the commit split:

    gh api repos/OWNER/REPO/contributors --jq '.[] | "\(.login) \(.contributions)"'

790 commits by one person against 20 by the author means the entry names that
person and claims only the part that is the author's.  The same command proves
the opposite where it is true: a repository whose entire contributor list is the
author is unambiguously theirs.

## Linking the evidence

Link the per-repository query, not GitHub search:

    https://github.com/OWNER/REPO/pulls?q=is%3Apr+author%3ALOGIN+is%3Amerged

It renders the merged pull requests with their titles to a signed-out visitor
(verified by fetching it and grepping the body for a known title).  The global
`https://github.com/search?...&type=pullrequests` page answers **429, "You have
exceeded a secondary rate limit"** to an anonymous request, so a reader who
follows it sees an error page.

## Two habits that carry the rest

+   **Read the body, not the status code.**  A 200 can be an archive banner over
    a superseded version, and a domain can resolve to a provider's sign-in page
    with a 403 while its repository still exists.  Both were live cases here.
+   **Say what was dropped and why, in the pull request.**  A claim removed for
    cause is a finding; a claim removed silently looks like an oversight, and
    the next session puts it back.
