---
name: typechecking-agda
description: Type-check Agda in the agda-native-air repository — benchmark obligation/gold fixtures under data/benchmarks/ and modules in the agda-dojang library — against the pinned toolchain. Use whenever Agda source has been added or modified and needs validation before commit.
---

# Type-checking Agda in agda-native-air

A gold solution or Agda module is not done until it type-checks under the pinned toolchain (Agda 2.8.0 + standard-library 2.3).  Type-checking is the test.

## Procedure

1. All Agda runs inside the flake shell, which registers `standard-library`, the repo-local `agda-dojang`, and (since #127) the flake-pinned `agda-algebras` store copy.  Never call a bare system `agda`.
2. The hook's `agda` wrapper is a shell FUNCTION and does not survive `--command`: `nix develop .#backend --command agda <file>` runs the bare binary and dies with `[LibraryError] Library 'agda-dojang' not found`.  From a non-interactive session, pass the flags explicitly — the same set the Scala components use (verified 2026-09-01 on the #127 tier):

   ```sh
   env -u LD_LIBRARY_PATH nix develop .#backend --command agda      --library-file=agda/libraries -l agda-dojang -l standard-library -l agda-algebras      -i <dir-of-the-file> <file>
   ```

   Both `--library-file` and `-i` are load-bearing; interactive shells can still use the bare `agda <file>` wrapper.
3. Check a single file first — it is fast and localizes errors; batch several files in one shell entry with `--command bash -c 'for f in …; do agda <flags> "$f"; done'` (the explicit flags work in child shells too).
4. To check every committed gold solution, run `make eval-benchmark` (the runner adds `--library agda-algebras` for that tier's rows itself); the CI slice is `make eval-benchmark-smoke`.
5. Do not stage generated artifacts: `*.agdai` and the nix-generated `agda/libraries` are gitignored.
6. `agda-algebras` fixtures need no checkout: the flake registers the store pin when `AGDA_ALGEBRAS_ROOT` is unset, and a live checkout overrides it.

## Checking a scratch module (observing what Agda actually prints)

Work on `agda-mcp` regularly needs Agda's *output* on a throwaway module — the exact text of an error, the shape of a warning header, whether a construct even reaches the checker.  Write the module outside the repo (the session scratchpad), then, from inside the shell:

```
agda --library-file="$REPO_ROOT/agda/libraries" -i "$SCRATCH_DIR" "$SCRATCH_DIR/Mod.agda"
```

Both flags are load-bearing, and omitting either costs a confusing failure:

+  Without `--library-file`, the wrapper's `--library agda-dojang` resolves against the nix-store default library file and Agda exits with `error: [LibraryError] / Library 'agda-dojang' not found` — even for a module importing nothing but `Agda.Builtin`.
+  Without `-i <dir-of-the-file>`, Agda resolves the module name against the include path it does have and exits with `[ModuleNameDoesntMatchFileName]`, listing every place the module could have lived.  The module name must still match the file stem; sibling helper modules in the same scratch directory resolve automatically once `-i` is set.

Agda 2.8.0 writes diagnostics to **stdout**, not stderr, so capture with `2>&1` rather than assuming stderr.

## Notes specific to this repo

+  Each benchmark module imports `AgdaDojang.Debug`; that resolves only inside the flake shell, where the `agda-dojang` library is registered — which is why a bare `agda` fails.
+  Obligation files under `obligations/` intentionally contain a `{!!}` hole and are not expected to type-check clean; only the matching `gold/` file must.
+  `agda-algebras` obligations check against the flake-pinned store library by default; export `AGDA_ALGEBRAS_ROOT=/path/to/agda-algebras` before entering the shell only to test against a live checkout.

## Reading common Agda errors

+  Unsolved metas / yellow: a term's type is under-determined; add an explicit type signature or annotate the ambiguous argument.
+  `x != y of type T`: a definitional-equality mismatch; check the lemma names and argument order in the equational chain.
+  "not in scope" after an import change: confirm the name and module path exist in standard-library 2.3, since names drift between stdlib versions.

## Quality gate (verify before declaring done)

+  The gold file type-checks with no errors and no unsolved metas.
+  Every definition has an explicit type signature, and the proof is the simplest correct term, not a token-count golf.
+  The obligation/gold pair, the `benchmark-index.jsonl` line, and the declared difficulty tier are mutually consistent.
