---
name: writing-a-corpus-linter
description: Build a new pure-Python checker over the agda-algebras literate corpus (a linter, an audit, a corpus extractor, or a figure the repository commits and must keep true) and wire it into the build the way the existing ones are — shared literate front end, tests beside the module, a Makefile target, a CI job, and a ratchet when the backlog cannot be cleared in one PR. Use whenever asked to audit, count, enforce, or harvest something across src/**/*.lagda.md, or when extending unused_imports.py / check_links.py / docstring_audit.py / corpus_stats.py. Includes the validation oracle that turns "I think the parser works" into proof.
---

# Writing a corpus linter for agda-algebras

The repository already carries several: `unused_imports.py`, `check_links.py`,
`gen_links.py`, `docstring_audit.py`, `corpus_stats.py`.  A new one is expected to look like them.
Read one before starting — `check_links.py` is the small model,
`docstring_audit.py` the large one.

## Never re-parse the literate format

`scripts/python/_utils/literate.py` is the shared front end.  Use it; do not
write another fence scanner.

+  `fences(text) -> tuple[Fence, ...]` — every ```` ```agda ```` block, each with
   `open_line`, `close_line`, `body`, the `prose` run preceding it, and
   `hidden` (the fence sits inside an `<!-- … -->` HTML comment).
+  `extract_agda_lines(text)` — one entry per source line, code or `''`.  Line
   numbering is preserved at every layer, so diagnostics point into the
   `.lagda.md`, never into a reconstructed buffer.
+  `clean_code_lines(...)` / `file_code_lines(text)` — the same with comments and
   string literals blanked, length-preserving so columns survive.  It blanks
   **pragmas too** (`{-# … #-}`), deliberately, so it is the wrong tool for
   anything that needs to read one.
+  `options_pragma(code)` — the `OPTIONS` Agda actually applies, or `None`.  Use
   this, never a search over the raw code: the raw search accepts a pragma that
   is commented out, which on `--safe` means calling a module safe on the
   strength of a line its author disabled.
+  `strip_front_matter`, `expand_target`, `gather_files`.

If a genuinely general helper is missing, add it *there* and prove the move is
output-neutral (see "Refactoring a live linter" below).

## Four facts about this corpus that break naive tools

1.  **Definitions are indented.**  Almost every public definition sits inside an
    anonymous `module _ … where`, not at column 0.  A column-0 detector finds
    almost nothing.  Anything that enumerates definitions needs Agda's layout
    rule: a stack of blocks, each knowing the column of its items *and* the
    column of the item that opened it (an empty inline `where` block otherwise
    swallows the rest of the file).
2.  **The preamble is hidden.**  Pragma, module header, imports and
    `private variable` live in a `<!-- ```agda … ``` -->` fence.  Agda sees it;
    a reader does not.  Decide explicitly which one your tool is modelling.
3.  **Prose is Markdown outside the fences.**  There are essentially no `-- |`
    docstrings, so any grep for comments reports the corpus as undocumented.
    Prose above a hidden fence renders immediately above the *next visible*
    fence — attribute it there.
4.  **`private variable` opens two layout blocks on one line**, and the items
    that follow are indented *less* than the inner keyword.  Give both blocks
    the outer line's column as their opener.

## The validation oracle: check the parser against Agda

Do not ship a parser that enumerates definitions on the strength of spot checks.
Agda will tell you the right answer.  With the agda-mcp server connected:

```
mcp__agda__exports_of  filePath=<ABSOLUTE path to the .lagda.md>  module=""
```

The empty string names the file's own top-level module, so the response's
`exports` is the exact set of value names the module exports, and `modules` the
nested modules it exports.  Diff that against your tool's output.

Pick modules that differ in *shape*, not in size: one plain module, one with
several `private` blocks, one with a named submodule.  Expect and account for
the deliberate differences — record constructors and fields appear in Agda's
export list but usually belong to their record for documentation purposes.

First call on a project root costs a load (seconds); consecutive calls about the
same file are milliseconds, and switching files pays another load.

## Layout, tests, Makefile, CI

+  Module at `scripts/python/<name>.py`, tests at
   `scripts/python/test_<name>.py`.  The `File:` docstring header is required.
+  Tests are dependency-free with a `_run()` tail that prints `N/N passed` and
   returns an exit code — copy the runner from `test_unused_imports.py`.  They
   must not need Agda; record the agda-mcp validation in the PR instead.
+  Two Makefile targets, `<name>` and `<name>-test`, added to `.PHONY`, with a
   comment block above them saying what the check is *for*.
+  A CI job in `.github/workflows/ci.yml` next to `link-check`: pure-Python jobs
   use `actions/setup-python`, run the test suite then the check, and must be
   added to **both** `needs:` and the `results=(…)` array of the `all-green`
   gate, or the gate silently ignores them.

## Ratchet, don't gate, when the backlog is large

A checker that fails on a pre-existing backlog blocks every PR and gets
reverted.  Take a `--max-gaps N` argument, fail only above `N`, print a nudge to
lower the ceiling when the count comes in under it, and pin `N` to today's count
in a Makefile variable (`DOCSTRING_MAX_GAPS ?= 201`).  CI then enforces the rule
from day one and the number only moves down.

## A number committed to a file: write it and check it

Some tools do not report findings; they produce a value that has to live in a
committed file (`docs/_links.md`'s generated sections, `docs/index.md`'s corpus
stats).  A build-time substitution is not enough.  `corpus_stats.py` exists
because the MkDocs hook recomputed the landing page's figures while *rendering*
and never wrote back, so the committed values, which are the ones GitHub shows,
went six weeks stale and were quoted elsewhere as current.  Build the pair, as
`gen_links.py` and `corpus_stats.py` both do:

+  the default run **writes** the value into the file, and is idempotent;
+  `--check` **verifies** it, printing a `difflib.unified_diff` and the single
   command that fixes it (`Run:  make corpus-stats`), and exits 1;
+  CI runs `--check`; the writer is its own Makefile target, for the author.

Two failure modes deserve explicit guards, because each lets a stale number pass
behind a green check:

+  **A marker the page no longer carries.**  When the substitution is anchored
   on `<!-- name -->…<!-- /name -->` pairs, a renamed or misspelled marker
   silently leaves the hand-typed value standing.  Fail when the page's marker
   set is not the tool's.
+  **A source of truth that cannot be read.**  When a value is derived from
   another file (a version from `agda-algebras.agda-lib`, `flake.nix`, or
   `mkdocs.yml`), a pattern that stops matching must be an error naming the
   pattern, never a check that quietly measures nothing.

Have the MkDocs hook import the tool instead of keeping its own copy of the
computation, so the built site and the committed file cannot disagree; and when
you replace a hook's private scanner with the shared front end, measure that the
two agree over the whole tree before the swap.

## Report blind spots as a number

Whatever the tool cannot classify must be counted and printed, not silently
dropped — otherwise a parser gap reads as a clean score.  Drive that tally to
zero across the whole corpus before believing any other number in the report.
In `docstring_audit.py` the last 49 stragglers were all clause heads (`f x with
e`, `f x ()`, `... | p`); threading the set of already-declared names is what
distinguishes a clause from a declaration.

## Refactoring a live linter

Moving shared code out of `unused_imports.py` is safe only if you prove the
output did not change.  Capture a *rich* baseline first — the clean tree
produces almost no findings, so use one that does:

```
python3 scripts/python/unused_imports.py --include-legacy --show-open-ended \
        --exit-zero --top 500 src > before.txt
python3 scripts/python/unused_imports.py --include-legacy --json --exit-zero src > before.json
```

Refactor, re-run, `diff`.  Byte-identical text *and* JSON, plus the existing
tests still green, is the bar.  See the `output-parity-harness` skill for the
general pattern.

## One traversal, two directions

An audit that asks "which definitions lack X?" is the inverse of an extractor
that asks "harvest X for each definition".  Build one walk and expose both — a
report and a `--json` record stream.  Key the records on `qname`
(`Module.Sub.name`), which is the join key with the Agda-internal (type, term)
corpus published by formalverification/agda-native-air; that extractor sees
types and terms but cannot see Markdown, so prose is the part only this
repository holds (issue #275).
