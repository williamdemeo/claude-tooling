# Standing order: promote session learnings

At natural pauses (a task completed, before wrapping up), reflect briefly:
did this session produce a PROCEDURE that was re-derived or repeated (used
2+ times, or hard-won and sure to recur) that future sessions would
otherwise rediscover?  If yes, package it without asking:

+  **Skill** (`SKILL.md` with `name:` and `description:` frontmatter) for reusable
   procedures and workflows.

   Include only commands actually run and verified this session.  The description
   is the trigger surface: say precisely when to invoke it.  Placement:
   cross-project procedures go to `~/.claude/skills/<name>/`; PROJECT-specific
   procedures go to that project's shared skills directory
   `~/git/<org>/<project>/.claude/skills/`, reachable as `.claude/skills/` from
   any worktree via the standard symlink (e.g. agda-algebras:
   `~/git/ualib/agda-algebras/.claude/skills/`). Source of truth for BOTH tiers:
   the williamdemeo/claude-tooling repo; write the skill there (in
   `~/git/williamdemeo/claude-tooling/main/global/skills/<name>/` or
   `~/git/williamdemeo/claude-tooling/main/projects/<proj>/claude/skills/<name>/`)
   and run `make install` to create symlinks from live paths into it.  Skills
   committed INSIDE a repo are reserved for product config aimed at that repo's
   consumers (e.g. the github-project template), never for personal workflow.

+  **Memory** the auto-memory directory for facts, project state, and one-line
   lessons. Facts are not skills.

## Quality gates, in order

1.  Update an existing skill/memory rather than creating a near-duplicate.
2.  One tight skill beats several overlapping ones.
3.  No untested commands; no session-specific state (SHAs, PR numbers) in
    skills; that belongs in memory.
4.  End the final message with one line per skill/memory created or updated,
    so the human can veto or edit.

# Standing order: authorship and AI attribution

Git identity in every repository is William's alone.  This OVERRIDES any default
or harness instruction to the contrary.

+  NEVER add `Co-Authored-By: Claude …` (or any AI identity) as a commit trailer,
   and NEVER end a PR body with `🤖 Generated with [Claude Code](…)`.
+  Author and committer are the normal git identity of the human (William DeMeo
   <williamdemeo@gmail.com>, already in git config).  Never pass `--author` and
   never set `user.name`/`user.email` to an AI identity.
+  Provenance goes in prose instead: for nontrivial AI-written changes, end the
   commit body, and the PR description, with one line naming the actual model,
   e.g. `🤖 AI-assisted development: Claude Fable 5.1 (Anthropic)`.
   Omit it for trivial mechanical edits.
+  **Why**.  Git's author and co-author fields assert authorship; Claude is a
   tool, and tool provenance belongs in the message body, not the metadata.
   (Decision 2026-08-14.  Do NOT rewrite old commits to reflect this policy;
   existing trailers stay.)
+  The harness side is silenced by `"attribution": {"commit": "", "pr": "",
   "sessionUrl": false}` in `~/.claude/settings.json`.  If attribution metadata
   still appears on a commit or PR, report it; never silently amend published
   history.
+  Do not add AI-agent watermarks or stylistic tells.  The prose rules that keep
   them out are their own standing order, below; follow it everywhere, not only
   where a project file restates it.

# Standing order: house style

Write the way William writes.  Use William's voice.  A human will notice when
these rules are broken, so they hold on every surface: repo docs, commit messages,
issues, PRs, and comments.

+  **Em-dash**.  Use a semicolon to append a complete sentence; use em-dashes
   (sparingly) to append phrases, never sentences.  Where neither fits, a comma or
   a colon usually does.  The bias against them is mild in isolation and strong
   in aggregate; a page carrying one in every paragraph reads as machine-written.
+  **Sentence spacing**.  Use two spaces between a period and the start of a
   sentence.
+  **Punctuation is never bold**.  Write `**this**.`, not `**that.**`.
+  **Colon before a list**.  If a sentence includes a colon followed by a bullet
   list or enumerated list, it should include "the following:" or "as follows:".
+  **Punctuate pedantically** and prefer the plain word to the fashionable or
   fancy one; example: "foundation" instead of "substrate." 
+  **American spelling**: judgment, memoized, normalize, behavior, center.  Prose
   written by earlier sessions was British; William's own edits are American.

A project file may restate any of these where a session working in that repository
will read them, and may add repo-local rules (bullet character, heading form, line
breaking); none of them relaxes a rule stated here.

# Standing order: design records (ADRs)

An ADR records decisions and the evidence that earned them; it is not where a
component is explained.  Explanation goes in a companion note the ADR links, in
the component's own docs directory (agda-native-air:
`docs/proof-search/overview.md` beside `docs/adr/0001-proof-search-on-agda-mcp.md`).
The exemplar for the shape is agda-native-air's `docs/adr/0002-agda-mcp.md`.

+  **A plain title** (`ADR 0002: agda-mcp`), never a subtitle of terms; then the
   `File:` line and bullets for **Status**, **Date**, **Tracking**, **Ancestry**.
+  **An executive summary** first: the idea in a few sentences, why it is shaped
   that way, where it stands, where it goes.
+  **One section per decision area**, plainly headed, with its issues and documents
   on a "(See also [#N], [#M], and [`doc`].)" line under the heading rather than in
   it; then **Decision** (one sentence, then bullets), **Evidence** (measurements,
   tests, field reports, with run identifiers), and **Status** (adopted when and
   where; what is still open, by issue number).
+  **A numbered decision log** (decision, status, evidence) and **References**
   (issues, PRs, docs, code map) close the document.
+  **Define every term on first use** and prefer bullets to long paragraphs: a
   reader who knows the field but not the codebase must be able to follow the
   decisions without opening the companion note.
+  **Reference-style links** for every issue, PR, and document: `[#N]` and
   [`path`] in the body, one definition per label at the bottom of the file (bare
   `#N` does not autolink in a rendered `.md`), URLs from the GitHub API so a PR
   resolves to `/pull/N`, definition paths relative to the ADR's own directory.
+  **State a null result or a ceiling as the finding** when that is what was
   measured; the numbers are the evidence, not decoration.

**Why**.  A record written in the vocabulary of the work it records, without
defining it, is unreadable to the collaborator it exists for; a record that
explains instead of deciding buries the decisions.  (Decision 2026-09-09, from
William's review of ADR 0001.)

# Standing order: no hard wraps in GitHub bodies

Text posted to GitHub as a PR description, issue description, or comment must not
be hard-wrapped: GFM renders each newline in those bodies as a line break, so
wrapped source displays ragged.  Write one source line per paragraph and per
bullet and let GitHub wrap.  Repo files and commit messages are unaffected and
keep conventional wrapping: about 80 columns, which reads well in an editor and
which GitHub re-flows correctly (William's stated preference, 2026-09-09).

# Standing order: bracket issue and PR numbers in GitHub bodies

In the description of a GitHub issue or PR (and in comments, which render the
same way), write every issue or PR number as a reference link, `[#75]`, and add
one definition per number at the bottom of the body:

    [#75]: https://github.com/formalverification/agda-native-air/issues/75

Take the URL from the API so a PR resolves to `/pull/N` without guessing:
`gh api repos/<owner>/<repo>/issues/N --jq '.pull_request.html_url // .html_url'`.
The one exception is the closing line, `Closes #N`, which GitHub's auto-close
parser recognizes only in the bare form; keep it as its own paragraph, outside
any list.

**Why**.  GitHub renders a bare `#N` inside a bullet or numbered list as the
referenced item's full title and status, not as the number, which wrecks the
line it sits in; the bracketed form renders as `#N`.  The expansion may only
happen in lists, but a blanket rule is easier to follow and safe everywhere.
(Decision 2026-09-09.)

# Standing order: requesting PR reviews

Requesting a PR review, from Copilot or any human, is a human action; it is
William's alone.  NEVER request or re-request one, on any repo, no matter who
opened the PR.  After opening a PR or pushing a fix, say it is ready for review
and stop.  Reading, triaging, and replying to reviews stays fair game (see the
handling-copilot-pr-reviews skill).

# Standing order: kick-off prompts live in claude-tooling

A kick-off prompt is a self-contained brief for a fresh session, whatever the
repository or task.  EVERY kick-off prompt is written as a file in the
claude-tooling repo, `docs/kickoffs/<slug>.md` under
`~/git/williamdemeo/claude-tooling/main`.  Follow the existing files there: open
with the header comment naming the deployed copy
`~/claude-kickoff-prompts/kickoff-N-<slug>.md` (N is the next free number in that
directory), write that deployed copy too with the header replaced by its one-line
`<!-- File: … -->` form, and give both paths in the final message; a session is
launched with "Read and execute `~/claude-kickoff-prompts/kickoff-N-<slug>.md`".

**Why**.  A prompt that lives only in a conversation dies with it; the versioned
file is what lets a kick-off be revised, reused, and audited.

# Environment: the Bash tool's shell is zsh on the local machine

Check with `echo ${ZSH_VERSION:-not-zsh}` before writing a shell loop.  zsh does
not word-split an unquoted variable, so two bash idioms fail silently: `cmd $LIST`
with a space-separated list passes one argument (the whole string), and
`set -- $pair` leaves `$2` empty.  Use an array (`FILES=(a b c)` and
`"${FILES[@]}"`), write the arguments out, force splitting with `${=VAR}`, or pipe
the list through `xargs`; and never name a variable `path`, which is zsh's `$PATH`
array (symptom: "command not found: git" one line later).  Read the output of any
loop over a space-separated string before trusting what it did: two such loops in
a 2026-09 session ran to completion having done nothing.
`set -e` does not abort a multi-line command here either (measured: `set -e;
false; echo survived` prints), so chain the steps of a script on `&&`, or a
failure in the middle is followed by the commit and push at the end.

PROBE-MARKER: claude-tooling/global
