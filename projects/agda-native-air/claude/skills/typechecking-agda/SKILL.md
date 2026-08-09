---
name: typechecking-agda
description: Type-check Agda in the agda-native-air repository — benchmark obligation/gold fixtures under data/benchmarks/ and modules in the agda-dojang library — against the pinned toolchain. Use whenever Agda source has been added or modified and needs validation before commit.
---

# Type-checking Agda in agda-native-air

A gold solution or Agda module is not done until it type-checks under the pinned toolchain (Agda 2.8.0 + standard-library 2.3).  Type-checking is the test.

## Procedure

1. All Agda runs inside the flake shell, which registers `standard-library` and the repo-local `agda-dojang` library and defines an `agda` wrapper: `nix develop .#backend --command agda <file>`.  Never call a bare system `agda`.
2. Check a single file first — it is fast and localizes errors.  For a benchmark gold file: `nix develop .#backend --command agda data/benchmarks/agda-stdlib-v0/gold/<Name>.agda`.
3. To check every committed gold solution, iterate the `gold` paths listed in `data/benchmarks/benchmark-index.jsonl`.
4. Do not stage generated artifacts: `*.agdai` and the nix-generated `agda/libraries` are gitignored.

## Notes specific to this repo

+  Each benchmark module imports `AgdaDojang.Debug`; that resolves only inside the flake shell, where the `agda-dojang` library is registered — which is why a bare `agda` fails.
+  Obligation files under `obligations/` intentionally contain a `{!!}` hole and are not expected to type-check clean; only the matching `gold/` file must.
+  `agda-algebras` obligations need a local checkout: set `AGDA_ALGEBRAS_ROOT=/path/to/agda-algebras` before entering the shell so the flake registers the library.

## Reading common Agda errors

+  Unsolved metas / yellow: a term's type is under-determined; add an explicit type signature or annotate the ambiguous argument.
+  `x != y of type T`: a definitional-equality mismatch; check the lemma names and argument order in the equational chain.
+  "not in scope" after an import change: confirm the name and module path exist in standard-library 2.3, since names drift between stdlib versions.

## Quality gate (verify before declaring done)

+  The gold file type-checks with no errors and no unsolved metas.
+  Every definition has an explicit type signature, and the proof is the simplest correct term, not a token-count golf.
+  The obligation/gold pair, the `benchmark-index.jsonl` line, and the declared difficulty tier are mutually consistent.
