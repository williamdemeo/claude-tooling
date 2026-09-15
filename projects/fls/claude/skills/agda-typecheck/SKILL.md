---
name: agda-typecheck
description: Typecheck Agda modules (.lagda.md / .agda) via the project's Nix flake. Use after editing any Agda module to verify it compiles, and before declaring Agda work done. Covers the `nix develop` invocation, the two-library layout (`src/` vs `formal-ledger-test/`, whose modules need `nix develop .#formal-ledger-test`), reading common Agda errors, and the project's Agda quality gate.  One caveat: if the user launches claude from inside the Nix shell, then you can drop the `nix develop --command` prefix from each of the command instructions described below.
---

# Typechecking Agda in Nix-based repositories

Agda code in Nix-based projects (e.g., formal-ledger-specifications, agda-algebras, agda-native-air) typechecks only through its Nix flake (it pins the correct Agda version and Agda libraries).  There is no system-wide `agda` on `PATH`.  However, the `agda` command may be available if the user launches Claude Code from inside a Nix shell.

> Prerequisite: typechecking when the agent is launched outside a Nix shell requires `nix` to be available and the network policy to permit the flake's substituters (`cache.nixos.org` and `cache.iog.io`) and flake inputs (`github.com`).
> On Claude Code on the web, provision this with a SessionStart hook (see `.claude/hooks/`) and a network policy that allows those hosts; otherwise these commands will fail and Agda cannot be checked here.

## Procedure

1. Enter the toolchain. All Agda commands run inside the flake shell: `nix develop --command <cmd>`. (The flake pins the correct Agda version and the supporting Agda libraries we use.)
2. Check edited module(s) only — fast, and it localizes errors: `nix develop --command agda src/Path/To/Module.lagda.md`.
3. Do not stage generated artifacts (`*.agdai`, `Everything*.agda`, `/.agda/`); they are gitignored.

## Two Agda libraries: `src/` and `formal-ledger-test/`

formal-ledger-specifications ships two Agda libraries, and the default flake shell
serves only the first, as follows:

+  `formal-ledger.agda-lib` (repo root; `include: src src-lib-exts`).  Modules under
   `src/` typecheck in the default shell: `nix develop --command agda src/...`.
+  `formal-ledger-test/formal-ledger-test.agda-lib` (`depend: ... formal-ledger`).  The
   default shell does NOT register `formal-ledger` itself, so every module here fails
   with `error: [LibraryError] Library 'formal-ledger' not found`.

**Agda picks the project `.agda-lib` by walking up from the CURRENT DIRECTORY, not from
the file argument** (verified 2026-09-08).  So `cd formal-ledger-test` first; invoking
`agda formal-ledger-test/src/Test/X.lagda.md` from the repo root picks the *root*
library instead and fails with `ModuleNameDoesntMatchFileName`, listing `src/Test/X` and
`src-lib-exts/Test/X` as the files it wanted.  (In Emacs this is a non-issue: agda2-mode
runs Agda in the file's own directory.)

Typecheck the test library from that package's own build environment:

```bash
nix develop .#formal-ledger-test --command bash -c 'cd formal-ledger-test && agda src/Test/Prelude.lagda.md'
```

That environment registers the prebuilt `formal-ledger` from the binary cache (a
~127 MiB fetch the first time, then ~20 s per module), and it resolves modules under
`src/` too, so it is a safe shell to launch an editor from when edits span both trees.
Two caveats: the ledger it registers is the store snapshot of `src/`, so local `src/`
edits are invisible to it; and it carries no `fls-shake` or `mkdocs`, so keep the
default shell for build-tool work.  Whole-library gate: `nix build .#formal-ledger-test`
(also cached, 29 MiB).

To check the test library against a WORKING COPY of `src/`, hand Agda a libraries file
that names the worktree's own `.agda-lib` (build it at the repo root, then `cd`):

```bash
nix develop --command bash -c 'set -e
FLS_LIBS="$TMPDIR/fls-libraries"
{ cat "$(sed -n "s/.*--library-file=\([^ ]*\).*/\1/p" "$(command -v agda)")"
  echo "$PWD/formal-ledger.agda-lib"; } > "$FLS_LIBS"
cd formal-ledger-test
agda --library-file="$FLS_LIBS" src/Test/Prelude.lagda.md'
```

A `--library-file` passed on the command line overrides the one baked into the flake's
`agda` wrapper (the wrapper's own flags precede `"$@"`, and the last occurrence wins).
This is also the only lever a user has: the wrapper's hardcoded `--library-file` means
`~/.config/agda/libraries` is ignored entirely.  Expect a long first run, since the
whole ledger is then typechecked from source (~16 min).

## Testing an alternative without touching the worktree

When reviewing a PR (or while a long gate is running in the worktree), test a
suggested rewrite in a scratch copy instead of editing the branch.  Agda finds
the `.agda-lib` by walking up from the CURRENT DIRECTORY, so the copy needs the
library file and both include dirs, plus the cache (verified 2026-09-08):

```bash
R="$SCRATCH/refactor"; mkdir -p "$R"
cp -r src src-lib-exts formal-ledger.agda-lib _build "$R"/
# edit files under "$R/src", then check from inside the copy:
cd "$R" && agda src/Ledger/Dijkstra/Specification/Epoch/Properties/Computational.lagda.md
```

Only the edited modules and their dependants re-check (about 1–2 min each on
the EPOCH spine).  Capture agda's own exit status, not the status of a wrapper
whose last command is an `echo`: a type error exits 42, a green run 0.  Diff
the copy against the worktree afterwards for a paste-ready suggestion.

Seeding caveat: seeding `_build/` from a sibling is only as good as the donor's
cache.  On 2026-09-08 a copy of `master/_build` (263 interfaces) still forced
229 modules to re-check (about 20 min) because the donor's interfaces did not
match its own sources; pick the sibling whose `.agdai` files are freshest.

## Reading common Agda errors

+ Unsolved metas / yellow highlighting: a term's type is under-determined; add an explicit type signature or annotate the ambiguous argument.
+ `x != y of type T`: a definitional-equality mismatch; check whether the development expects setoid equality rather than propositional `_≡_`.
+ `No instance of ...`: a missing import, or an instance argument not in scope.
+ `rewrite' did not apply`: the equation's left-hand side no longer occurs in the goal once Agda normalises it; typical when the LHS is a `where`-bound abbreviation of a record literal (projections out of it reduce away).  State the equality with explicit `cong`/`cong₂`/`trans` instead of `rewrite`.

## Extending a wide record: the typechecker is not a complete gate

Adding a field to a record with mechanical companions (`PParams` and its
`PParamsUpdate`, `modifies*Group`, `applyPParamsUpdate`; `StakePoolParams` and
its `Foreign` conversions) has a failure mode the typechecker cannot see: a
`Bool`-valued group predicate or a positivity list that simply *omits* the new
field still typechecks.  Three habits, in order:

1. Warm the closure BEFORE the first edit — run the full-closure typecheck in
   the background while you compose the patch, so later runs re-check only the
   modules your edit touches instead of the whole library.  For a FRESH
   worktree (e.g. checking out someone else's PR branch), seed its cache first
   by copying `_build/` from a sibling worktree of the same repo: interface
   files are content-keyed, so matching modules are reused and stale ones are
   simply rebuilt (verified 2026-08-31: a cold 98-module Dijkstra gate finished
   in minutes off a seeded cache).
2. Split the change into patches that each typecheck on their own, and commit
   each one; a failure then localizes to one patch, and every commit is green.
   Adding fields + `applyPParamsUpdate` is one patch; changing the *type* of a
   predicate (e.g. `paramsWellFormed` gaining a conjunct) is another, since that
   ripples to every pattern match on it.
3. Assert placement mechanically.  A throwaway script that checks each new field
   name appears in each region it must (record, update record, each group
   predicate, the apply function, each well-formedness list, the prose field
   list) catches exactly what the typechecker will not.

## Quality gate (verify before declaring done)

+ Every new public definition has an explicit type signature.
+ New lemmas are named, not inlined into opaque `rewrite` chains.
+ No `let` bindings are used if a `where` block *below* the proof could be used instead.
+ Helper functions and pattern matching are used instead of the `with` construction, unless the `with` substantially simplifies the presentation.
+ No new synonym was introduced for an existing concept.
+ Inline Agda names in prose use kramdown spans, e.g. `` `S`{.AgdaFunction} ``, `` `MySetoidModule`{.AgdaModule} ``.


