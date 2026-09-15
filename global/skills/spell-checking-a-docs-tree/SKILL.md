---
name: spell-checking-a-docs-tree
description: Add a hunspell spell check with a curated project dictionary to a Markdown docs tree and wire it as a Nix flake check, without the hundreds of false positives a default dictionary produces on technical prose. Use whenever a repo wants a spell-check gate, whenever a spell check reports a wall of "unknown" words that are all real vocabulary, or when a checker that passes locally fails inside `nix flake check`. Covers the stripping rules that decide what is prose, hunspell's pipe mode, the four capitalization and hyphenation rules that decide what a dictionary entry can be, and keeping the dictionary from rotting into a silencer.
---

# Spell-checking a docs tree

Measured on williamdemeo.github.io, 2026-09-12: 59 pages, 56,831 words.  A
plain `hunspell -d en_US` run reported **579 unknown words and not one
misspelling**.  With the rules below the same corpus reports zero, and a
planted typo is found.  The dictionary is the work; the tool is incidental.

## Order of operations

1. Write the stripper first and measure what it lets through.  Do not curate a
   dictionary until the report is free of markup fragments, or a third of the
   entries will be things no reader can see.
2. Measure against **the dictionary the gate will use** (see the nixpkgs trap).
3. Curate the remainder into a grouped word list.
4. Add the self-audit that keeps the list honest.
5. Verify in both directions: plant a typo, and plant one in each masked region.

## What counts as prose

Everything a reader reads and nothing else.  Each rule below was added because
a word no reader can see reached the report; the parenthesized word is the one
that arrived.

| Strip | Because |
| --- | --- |
| fenced code, inline code spans, HTML comments | `teh` in an example is not a typo |
| YAML front matter, except `title:` and `description:` | the rest is configuration; those two are published |
| `$...$`, `$$...$$`, `\(...\)`, `\[...\]` | (`mathbf`) |
| `\begin{env}...\end{env}` | math outside any delimiter (`mathbf`, `thm`) |
| inline link destinations `](...)`, reference definitions, bare URLs, autolinks | file paths and host names |
| HTML tags, attribute lists `{ .cls }` | markup |
| snippet directives (`--8<--`), footnote markers, emoji shortcodes | markup |
| LaTeX cross references in either bracket, `[ex:a-b]` and `(eq:2)` | (`oper`, `eq`) |
| a whole word containing an HTML entity | `Fran&#231;ois` splits into (`Fran`, `ois`) |

Keep image **alt text**: a screen reader reads it aloud.

Two rules that are easy to get wrong:

- **Inline math may wrap a line, and must not cross a blank line.**
  `\$[^$\n]+\$` misses an expression that wraps; a pattern with no blank-line
  guard lets one unpaired `$` swallow the rest of the page.  Use
  `\$(?:[^$\n]|\n(?![ \t]*\n))+?\$`.
- **A code span must not cross a blank line either**, for the same reason: a
  stray backtick in one paragraph and another pages later would mask every
  link and word between them, and the run would still report success.

Mask with a same-length, same-shape replacement (newlines preserved) so
offsets survive and a finding is reported at its real line.

## Tokenizing

```python
TOKEN = re.compile(r"(?<![\w'’-])[^\W\d_][\w'’-]*", re.UNICODE)
```

- The lookbehind matters: without it the scan starts inside `404ing` and
  yields (`ing`).
- Keep hyphens in the token; hunspell breaks them itself and reports the half
  that failed, which is what lets you locate the word.
- Strip a trailing possessive, then strip trailing `'` and `-`.
- Skip a token containing a digit or an underscore: that is an identifier.
- Skip a token with no ASCII letter, and ignore a **reported part** with none:
  `Σ-typed` should not put `Σ` in a dictionary.

## hunspell, in pipe mode

Use `-a`, not `-l`.  `-l` prints the offending word with no way back to the
token it came from: hunspell breaks `par-alg-rep` and reports `alg`, which
appears nowhere in the source.

```python
cmd = [hunspell, "-a", "-d", dictionary, "-i", "UTF-8"]
if personal: cmd += ["-p", str(personal)]
got = subprocess.run(cmd, input="".join(f"^{t}\n" for t in tokens), ...)
```

- `^` prefixes each line so a token starting with one of pipe mode's command
  characters (`*&#@~+-!$`) is read as a word.
- One output block per input line, blocks separated by a blank line, **after a
  one-line `@(#)` banner**.  Remove the banner as a *line*, not as the first
  block: it is followed by a single newline, so the first token's block is
  glued to it and every verdict after that lands on the wrong word.  That
  reads as a checker that works and is off by one.
- A misspelling is a line starting `& word …` (has suggestions) or `# word …`
  (has none).

## The four rules that decide what an entry can be

Measured, not assumed:

1. **hunspell breaks a hyphenated word before consulting any dictionary.**  A
   hyphenated entry (`agda-algebras`) is never reached.  Carry the fragment
   (`agda`) instead, under a heading that says why.
2. **A lowercase entry accepts the capitalized and all-caps forms; the reverse
   does not hold.**  `agda` accepts `Agda` and `AGDA`; `Agda` accepts neither
   `agda` nor `AGDA`.
3. **Mixed case needs its own entry.**  `mkdocs` does not accept `MkDocs`,
   `arXiv`, `UACalc` or `WeasyPrint`.  Carry both spellings.
4. **The personal dictionary does no affix expansion.**  `setoid` does not
   admit `setoids`.  Curate from the measured report, which already contains
   every form the corpus uses.

Some en_US word lists break a **contraction** at the apostrophe too, so
`couldn`, `didn`, `doesn` and `isn` become entries.  Check before assuming a
tokenizer bug.

## The nixpkgs trap

`nix eval nixpkgs#hunspellDicts.en_US` resolves through the **registry**, not
through the flake's pinned `nixpkgs`.  On nixos-25.05 the pinned dictionary is
`hunspell-dict-en-us-wordlist-2018.04.16`; the registry's was 2026.02.25, and
the 2018 list is 25 words poorer and breaks contractions.  A dictionary
curated against the wrong one passes locally and fails in the sandbox with a
wall of new words.

Curate through the gate's own environment:

```zsh
nix develop --command make spell-check     # dev shell -> flake's nixpkgs
```

and set `DICPATH` in both the dev shell and the check so no target needs a
flag:

```nix
DICPATH = "${pkgs.hunspellDicts.en_US}/share/hunspell";
```

`cd ${proseSource}` inside the check, so a finding reads `docs/about.md:67`
rather than a store path with that on the end of it.

## The word list

One word per line, `#` comments, **grouped by where the words come from**.  The
grouping is not decoration: a word that is not in the list is either a
misspelling or real vocabulary, and which heading it would go under is the
fastest way to tell which.  Headings that earned their place on a mathematics
site: the proof assistants, the subject's own terms, mathematics generally,
people, journals and citation abbreviations, scholarly services, the
toolchain, typography, software and the web, places and institutions, the
project's own names, host names written as link text, English the dictionary
lacks, and fragments.

## Keeping it honest

A dictionary only grows, and an entry in it for no reason silences a typo
forever.  A clean run should also report:

- entries the base dictionary already knows (ask hunspell **without** the
  personal dictionary);
- entries no longer found anywhere in the corpus.

Both are **notes, not failures**: deleting a page should not fail a build until
somebody prunes a word list.  Put the failure behind `--strict`, which is what
to run when pruning.

The "unused" test has a false-positive class that will bite: compare
case-insensitively **and** against hyphen-split parts, or it reports `alg`,
`ary`, `mortem` and every lowercase entry as dead and a prune deletes the
entries holding the check up.

## Scope

Exclude a file generated from an external source (issue text, a CMS export).
A typo there cannot be repaired in the file, and its vocabulary changes
whenever the source does, which makes the dictionary a moving target and the
gate a blocker on unrelated work.  Leave it reachable by hand:
`make spell-check PROSE_ROOT=docs/GITHUB_PROJECT.md`.

Say in the docstring what a source-side check cannot see: pages rendered from
YAML or JSON at build time never pass through it.

## Verify in both directions

Plant a misspelling in prose and in a `title:`, and the same word inside a code
span, a fence, math, a link target, a snippet directive and an HTML entity.
The first two must be reported and the rest must not.  Then mutate the
stripper (drop the math-environment rule, drop the front-matter title) and
confirm the suite fails.  A check only ever observed passing may be looking at
nothing.
