---
name: writing-a-docstring-pass
description: Write the prose blocks for one subtree of agda-algebras' docstring backlog (issue #268 and its per-subtree sub-issues #540–#547) and land it as a provably prose-only PR — scope with docstring_audit.py, ground every paragraph in a source you have read, prove the extracted Agda is byte-identical to master, and lower the Makefile ratchet to the measured count. Use whenever asked to add or improve module headers or per-fence prose in src/**/*.lagda.md, or to close one of the #268 sub-issues. Covers the six traps that cost real time.
---

# Writing a docstring pass

One sub-issue of #268 per PR.  The work is prose only: no Agda changes, no
reformatting, no reflowing pre-existing wrapped paragraphs.

## Read these first, in this order

1.  The sub-issue (`env -u GH_TOKEN gh api repos/ualib/agda-algebras/issues/N --jq '.title, .body'`; plain `gh issue view` fails on this org's classic Project).
2.  **#268's body** — the conventions, grounding discipline and verification checklist live there once and are not repeated in the children.
3.  `docs/adr/010-documentation-coverage-policy.md`.
4.  `docs/STYLE_GUIDE.md` §§ "Every public definition has a prose comment block", "Module headers have comment blocks".
5.  `src/Setoid/Algebras/Basic.lagda.md` — the exemplar (#538).  Match its register.

## The bar is settled

Prose attaches to the **code fence**, not to the individual definition.  Every
fence gets a real paragraph; every module opens with more than the boilerplate
`This is the [X][] module of the …` sentence.  One definition per fence is
rejected repository-wide (ADR-010) — a fence may cover a family, and should when
the definitions genuinely are one.  Where a block covers several, **name each of
them**; that is the `named` column and the join key for the #275 extractor.

Do not split, move or reindent a fence.  Everything you add goes *outside* the
fences.

## Scope the work

```
make docstrings-list                                       # every gap, repo-wide
python3 scripts/python/docstring_audit.py <path> --list --modules --exit-zero
```

`--modules` is the second half of the bar (weak headers) and is easy to forget.
Several paths may be passed at once, which is how you get one figure for a
subtree plus its barrel.

## Wrapping, and the wraps that break the page

Hard-wrapping is **allowed** (`docs/STYLE_GUIDE.md` § "Wrapping prose", settled in
PR #549 after #548 raised it).  The choice is per file: match what the file already
does, never mix the two forms inside one file, and do not reflow a paragraph you
are not otherwise changing.  Most of the corpus wraps at roughly 80 columns, so
new prose in an existing module usually wraps too.

Three wraps break the rendered page, and the first two fail silently in source:

+  **between an inline code span and its `{.AgdaFunction}` braces** — `attr_list`
   needs them adjacent, so the attribute is dropped and the braces render as
   literal text.  This is the expensive one: attribute spans mark up every Agda
   name in the corpus.
+  **inside a reference-style link's label at a point with no space** —
   `[Setoid.Algebras.\nProducts][]` becomes the label `Setoid.Algebras. Products`,
   matches no definition, and renders literally.  Breaking at a space the label
   already contains is fine.
+  **inside an inline code span** — it renders, since the newline collapses, but
   the span stops being greppable.

GitHub PR, issue, and comment bodies are the opposite case and must **not** be
wrapped: GitHub renders every newline there as a `<br>`.

## Ground every paragraph, or cut it

A comment that restates the type signature in English fails the bar.  The three
sources that actually carry usable prose:

+  `docs/STYLE_GUIDE.md` § "Every public definition has a prose comment block" has a model paragraph for `hom` verbatim.
+  `src/Examples/Demos/HSP.lagda.md` is the published TYPES 2021 paper as a literate module: expository prose on homomorphisms, mono/epi, products, factorization, terms, free algebras.  Mine it.
+  the frozen `src/Legacy/Base/**` analogue of the module often explains *why* a construction exists (`Legacy/Base/Algebras/Products.lagda.md` on why `ℑ` is needed is the clearest case).  Cite the idea, not the module.

Then **grep before you claim**.  Every "this is used by X" and every "X is
defined to be this" in a docstring is checkable in one command, and roughly one
in four of them is wrong on the first draft.  Two real examples from #539:

+  "the first homomorphism theorem is proved from `HomFactor`" — false; `Noether` imports only `kerquo` and `πker`, and the sole consumer of `HomFactor` is `Setoid/Varieties/HSP.lagda.md`.
+  `mon→intohom`'s result type *is* `_IsSubalgebraOf_` and `epi→ontohom`'s *is* `_IsHomImageOf_` — true, and worth saying, but only discovered by grepping for the definitions.

Where the mathematics needs the author, leave `<!-- TODO(#268): … -->` saying
what you would need to know.  A TODO does **not** satisfy the checker; that is
deliberate.  A short list of "I could not write this one, and why" is a better
deliverable than plausible filler.  Cutting an unsupported clause is always
better than hedging it.

## Prose rules William has set (2026-08-26)

+  **No em-dashes** in anything composed for him: documentation prose, PR and
   issue bodies, commit messages.  Semicolon for a complete sentence, comma or
   colon for a phrase, parentheses for a parenthetical.  En-dashes in name pairs
   (Pálfy–Pudlák) are fine.
+  **No issue or PR numbers in documentation prose** (`src/**/*.lagda.md`).  An
   ADR may be cited by number, preferably in a footnote.  GitHub bodies may
   reference numbers freely.
+  Gate both before every commit; each must come back empty:

```
git diff -- 'src/*' | grep -E '^\+.*—'
git diff -- 'src/*' | grep -E '^\+.*#[0-9]{3}'
```

## Where the prose goes

+  **Module header**: the run of prose before the **first** fence, hidden or not.  So in the corpus idiom `heading / boilerplate / <!-- preamble fence --> / prose / first visible fence`, the paragraphs that look like a header are attributed to the *fence*, and the module still counts as boilerplate.  Insert **above the `<!--`**.
+  **Fence prose**: immediately above the fence, after the `-->`.  Prose carries across a hidden fence, since a preamble renders as nothing.

## Prove it is prose-only

Do not assert this; run it.  Drop this in a scratch directory (it uses the
repository's own literate front end, so it sees exactly what Agda sees):

```python
import subprocess, sys
from pathlib import Path
sys.path.insert(0, "scripts/python")
from _utils.literate import extract_agda_lines

def fence_bytes(text):
    return "\n".join(ln for ln in extract_agda_lines(text) if ln != "").encode()

rev, paths = sys.argv[1], sys.argv[2:]
bad = 0
for p in paths:
    old = subprocess.run(["git", "show", f"{rev}:{p}"], capture_output=True,
                         check=True).stdout.decode()
    same = fence_bytes(old) == fence_bytes(Path(p).read_text())
    print(f"{'OK  ' if same else 'DIFF'}  {p}")
    bad += not same
sys.exit(1 if bad else 0)
```

```
python3 prose_only.py master $(git diff --name-only -- 'src/*')
```

Blank filler lines are dropped because inserting prose shifts line numbers; the
code lines themselves must match exactly.

## Lower the ratchet to the measured count, not by subtraction

`DOCSTRING_MAX_GAPS` and `DOCSTRING_MAX_WEAK_HEADERS` in the `Makefile` drift
*above* the true count, because a PR that clears gaps does not always lower them
(#538 left four gaps and one header of slack).  Measure master rather than
subtracting from the recorded value:

```
git worktree add --detach /tmp/wt-master master
cd /tmp/wt-master && python3 scripts/python/docstring_audit.py --modules --exit-zero src | grep -E '^TOTAL|no real header'
git worktree remove /tmp/wt-master
```

Do not `git archive` the tree into a scratch directory instead — the audit's
exclusions are path-sensitive and the figures come out wrong (3267 definitions
instead of 3226).  Then set both variables to the *post-change* measured
numbers, so no slack survives, and say in the PR body why the drop exceeds what
the PR itself cleared.

## Two things about worktrees

**Parallel branches conflict on the ratchet, and only there.**  Each sub-issue
branch measures master and sets its own post-change ceiling, so N branches off the
same master give an N-way conflict on `DOCSTRING_MAX_GAPS` and
`DOCSTRING_MAX_WEAK_HEADERS` — and taking any one side leaves the ceiling too
high.  The correct post-merge value is master minus the *sum* of what the branches
clear.  Say so in each PR body, with a table, and tell the reviewer to re-measure
rather than trust the arithmetic.  The subtrees themselves are disjoint, so
nothing else conflicts.

**agda-mcp only serves one worktree.**  Its libraries file registers
`agda-algebras` at a single root, so `check_file` on a file from another worktree
fails with `rootMismatch` naming both roots.  That is the guard working, not a
bug.  Use the CLI from inside the target worktree instead:

```
cd <worktree> && nix develop --command agda src/Path/To/Module.lagda.md
cd <worktree> && nix develop --command make check
```

The flake's shellHook provisions that worktree's own `.agda/libraries` and `agda`
wrapper on first entry, so this works even in a worktree nobody has entered
interactively.  Warm the interfaces once (check the subtree barrel) before the
per-file sweep, or the first call pays for the whole dependency cone.

## Verify, all of it

```
python3 prose_only.py master $(git diff --name-only -- 'src/*')   # 9/9 OK
for f in $(git diff --name-only -- 'src/*'); do agda "$f" || echo "FAIL $f"; done
make check-links        # gen_links --check, then all reference links resolve
make docstrings         # exit 0 at the new ceilings
make docstrings-test    # 72/72
make check              # the real CI gate; slow, Legacy dominates
```

`agda-mcp`'s `check_file` also works and resolves `nearest-agda-lib` to the
worktree correctly, which is worth knowing because the `agda` on `PATH` inside
`nix develop` hard-codes `--library-file` for the worktree the shell was entered
from.

## The traps

+  **A barrel module is not in its own subtree directory.**  `src/Setoid/Algebras.lagda.md` is *not* matched by `docstring_audit.py src/Setoid/Algebras`; pass it explicitly.  A barrel declares nothing, so it has no gaps — only a header, whose content should say what the theme is and which submodule to reach for, derived from the `open import … public` list.
+  **`make docstrings` is silent when you land exactly on the ceiling.**  It prints the `✓ … lower DOCSTRING_MAX_GAPS to N` nudge only when strictly below.  Trust the exit code, not the text.
+  **Do not copy a cross-reference out of the style guide without checking it.**  Its model `hom` paragraph cites `∘-hom`, which exists only in the frozen `Legacy/Base` tree; the Setoid name is `⊙-hom`.
+  **Kramdown span classes must match the Agda kind.**  Confirm against existing corpus usage rather than guessing, with ``grep -rho "`Name`{\.Agda[A-Za-z]*}" src/ | sort -u``.  Record constructors are `.AgdaInductiveConstructor`; a record's derived members (`HomReduct`) are `.AgdaFunction`; predicates that are really functions returning a type (`IsInjective`, `IsSurjective`) are `.AgdaFunction`, not `.AgdaRecord`.
+  **Every reference-style label must already be in `docs/_links.md`** or `make check-links` fails.  Do not hand-edit that file; it is generated (`make gen-links`).
+  **Nothing catches a dangling footnote reference.**  `check_links` only checks reference-style links, so a `[^1]` with no `[^1]:` definition passes every gate and renders as literal text.  Check it yourself: compare `(?<!^)\[\^([^\]]+)\](?!:)` against `^\[\^([^\]]+)\]:` per file.
+  **Keep the PR body's claims exactly true, and re-check them after the author pushes.**  Copilot reads the body as a contract and audits against it: on #548, five of nine findings were the same "the fence is not byte-identical, contrary to your stated contract" observation restated once per file, because revisions on top of the first commit had added semantics-preserving Agda cleanups.  Re-run the fence diff after every push, including the author's, and correct the body rather than reverting the author's work.  When you decline a suggested remedy, say which one and why.
+  **Fixing a defect in a header you are rewriting anyway is in scope; say so in the PR.**  #539 found a stray quote in one YAML title, an `Isomoprhisms` typo in another, and an opening sentence naming the wrong module.  Leaving a wrong module name directly above new prose is worse than the one-line diff.

## The PR

Standing authorization to open one covers this work.  Name which paragraphs are
yours (all of them, normally) and the two or three you are least confident in,
with the reason — William reviews the mathematics and needs to be pointed at the
soft joints, not at the whole diff.  State plainly whether any `TODO(#268)`
markers remain.  Never request a review.
