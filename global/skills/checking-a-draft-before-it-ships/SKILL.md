---
name: checking-a-draft-before-it-ships
description: Prove a draft's claims and test it on the reader it is written for, before it goes out under William's name - mechanically verify every quoted snippet against the source repository at a named commit, and put the rendered page in front of a role-played subagent reader who reports what it could not follow and did not believe. Use before publishing any prose that quotes code, cites a measurement, or is aimed at a specific audience: a blog post, a project page, the research statement, an ADR, a cover letter. Covers the extraction and the byte-for-byte check, what a useful reader persona looks like, the five-part report that makes the answers actionable, and which findings to act on.
---

# Checking a draft before it ships

Two failure modes sink writing that is supposed to be evidence.  A quoted
snippet that drifted from the source, which the one reader who checks will
find; and a paragraph the intended reader cannot follow, which everyone finds
and nobody reports.  Both are cheap to catch and neither is caught by reading
the draft again yourself.

Verified 2026-09-13 while writing three technical posts for williamdemeo.org,
where the quote check confirmed nine snippets against another repository and the
reader test returned four findings, one of which was an argument that was simply
wrong.

## Quotes: extract from the commit, then prove it

Never retype a snippet and never trust a copy.  Read it out of the source
repository at a pinned commit, and check afterwards that what is in the draft
is still a substring of that file.

```zsh
cd ~/git/<org>/<repo>/<checkout>
git rev-parse HEAD                       # the commit the post will name
git status --short                       # tracked files must be clean, or the
                                         # file you read is not the file you cite
git show <commit>:<path> | sed -n 120,135p
```

`git show <commit>:<path>` rather than opening the working copy: a worktree can
carry uncommitted edits, and a post that quotes one is quoting something no
reader can fetch.  (Untracked files are harmless; modified tracked ones are
not.)

Then verify every fenced block at once, rather than the one you remember
changing:

```python
import re, subprocess, pathlib
post = pathlib.Path("<draft>.md").read_text()
blocks = re.findall(r"```agda\n(.*?)```", post, re.S)     # the fence's language
sources = {p: subprocess.run(["git", "show", f"{COMMIT}:{p}"],
                             capture_output=True, text=True).stdout
           for p in PATHS}
for block in blocks:
    for chunk in (c for c in block.split("\n\n") if c.strip()):
        hit = [p for p, text in sources.items() if chunk.rstrip("\n") in text]
        print(f"{chunk.splitlines()[0][:48]!r:52} -> {hit or 'NOT FOUND'}")
```

Splitting a block on blank lines matters: a block usually stitches two or three
separate definitions together, and a whole-block match would fail on the
stitching while each piece is verbatim.

Three rules the check cannot enforce, which are yours:

+  **Name the module path and the commit in the post.**  A snippet nobody can
   locate is not evidence.  One line at the end naming the repository, the
   branch and the short commit covers a whole post.
+  **Say when a quotation is trimmed**, and trim rather than edit.  Eliding
   absolute paths from a captured JSON response is fine if the post says the
   paths were shortened.
+  **A quoted sentence keeps its own punctuation.**  House style bans the em
   dash in what you write, not in what someone else wrote, so quote a fragment
   that does not contain one or mark the elision, and never silently repunctuate
   a quotation.

## Numbers: one source file, and its run identifier

The same discipline, less machinery.  Every figure in the draft is read from a
named file in the session that writes it, carries the run identifier the source
carries, and is attributed to the configuration it was measured on.  Two traps
found this way in one afternoon: a wall-clock time attached to the wrong sweep
of three with the same solve count, and a control's headline read as "every
needle" when the number beside it was the sweep's total.  Both survive rereading
and neither survives asking "which row of which table is this".

## The reader test

Build the page first: a reader test on Markdown tests the wrong artifact, and
the rendering is where a dangling link or an unexplained code block shows up.
For an MkDocs site, build it and reduce one page to what a reader reads:

```python
import re, html, pathlib
src = pathlib.Path("site/<path>/index.html").read_text()
body = re.search(r'<article\b.*?>(.*?)</article>', src, re.S).group(1)
body = re.sub(r'<(script|style|nav)\b.*?</\1>', '', body, flags=re.S)
body = re.sub(r'<h([1-6])[^>]*>', lambda m: '\n\n' + '#' * int(m.group(1)) + ' ', body)
body = re.sub(r'<(p|li|pre|tr)\b[^>]*>', '\n', body)
body = html.unescape(re.sub(r'<[^>]+>', '', body))
pathlib.Path("<scratchpad>/as-rendered.txt").write_text(
    re.sub(r'\n{3,}', '\n\n', body).strip() + "\n")
```

Then spawn **one** subagent, with no other context, and give it four things.

+  **A persona with a stated gap.**  Not "a technical reader": the exact reader
   the piece is aimed at, plus the specific thing they do not know.  "A strong
   engineer who evaluates candidates for AI and verification roles, reads ML
   papers, and has never used a proof assistant" produces findings; "a smart
   reader" produces compliments.
+  **A file path, and a ban on everything else.**  No web search, no reading the
   repository, no verifying claims against other sources.  The value of the test
   is that the reader is cold, and an agent that goes and reads the ADR will
   understand the post for the wrong reason.
+  **Permission to be blunt**, in those words.  "A polite answer is useless
   here" is worth a paragraph of instructions.
+  **A fixed report structure**, so the answers are usable rather than a review:

   1.  *Where I stopped understanding*, quoting the sentence and naming the term
       or the leap that did it.  Ask for the two hardest passages even if it
       followed everything.
   2.  *What I did not believe*, including anything that made it trust the
       author **more** than expected and why.  That half tells you which
       paragraphs to keep when cutting.
   3.  *What I would ask in an interview*, "including any question that is
       really a doubt in disguise".
   4.  *The honest verdict*, one paragraph, on whether it wants to talk to the
       author.
   5.  *The three edits I would make*, in priority order, naming the sentence.

## What to do with the answers

Not all of it, and not none of it.  Sort the findings into four piles.

+  **Errors of fact in your phrasing**: fix immediately, they are the point of
   the exercise.  Both of this session's were sentences where a number and a
   claim came from different rows.
+  **A missing explanation at the first hard artifact**: fix, and fix it early
   in the piece.  A reader who bounces off the first code block never reaches
   the paragraphs that would have convinced them, and they will not tell you.
+  **An argument the reader says is wrong**: check it, and if they are right,
   say so in the text rather than deleting the claim.  The "three seconds per
   label is a wall" argument was wrong because the work is embarrassingly
   parallel; the repair was two sentences saying what does not parallelize.
+  **Verdicts about the author rather than the draft**: do not edit them away.
   "No machine learning anywhere in this piece" was accurate, and the answer was
   to state the framing in the first paragraph, not to imply otherwise.

The test is worth running once per piece, not iteratively.  A second cold reader
on a revised draft costs as much and finds less, and the reader you most need is
the one who has not seen it before.
