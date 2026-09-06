---
name: typechecking-agda
description: Type-check Agda modules in the agda-algebras repository after editing any .lagda.md file, and verify the change meets the library's corpus-quality bar. Use whenever Agda source has been added or modified and needs validation before commit.
---

# Type-checking changes in agda-algebras

Type-checking is the only test this library has; a change is not done until it type-checks.

This skill is the final gate, not the development loop.  When the agda-mcp server is connected (see the standing order in the project CLAUDE.md), draft Agda hole-by-hole through it and reserve the full nix develop typecheck for the end of a work unit.

## Procedure

1. Enter the toolchain.  All Agda commands run inside the flake shell: `nix develop --command <cmd>`.  The flake pins Agda 2.8.0 and standard-library 2.3.
2. Check the edited module(s) first, before the whole library — it is faster and it localizes the error; the command (unless type-checking interactively with the agda-mcp server): `nix develop --command agda src/Path/To/Module.lagda.md` 
3. Before committing, run the full check exactly as CI does: `nix develop --command make check`.
4. Do not stage generated artifacts (`*.agdai`, `Everything*.agda`, `/.agda/`); they are gitignored.

## Reading common Agda errors

+  Unsolved metas / yellow highlighting: a term's type is under-determined; add an explicit type signature or annotate the ambiguous argument.
+  "x != y of type T": a definitional-equality mismatch; check whether the development expects setoid equality (`Setoid/`) rather than propositional `_≡_`.
+  "No instance of ...": a missing import, or an instance argument not in scope.
+  Scope error after a rename: confirm the symbol is not part of an in-flight deprecation (`∣_∣` / `∥_∥` → `proj₁` / `proj₂`).

## Quality gate (verify before declaring done)

+  Every new public definition has an explicit type signature.
+  New lemmas are named, not inlined into opaque `rewrite` chains.
+  No new synonym was introduced for an existing concept.
+  Inline Agda names in prose use kramdown spans, e.g. `` `S`{.AgdaFunction} ``.

## Per-worktree Agda wrapper

Development uses one git worktree per branch under `worktrees/`.  The `agda` on `PATH` inside `nix develop` is a wrapper that hard-codes `--library-file` for the checkout the shell was entered from, so checking a different worktree with it resolves modules to the wrong tree (`ModuleDefinedInOtherFile`).  The flake's shell hook writes that wrapper for whichever checkout it is entered from (`$ROOT/.agda/{libraries,defaults,bin/agda}`, with `$ROOT` from `git rev-parse --show-toplevel`) and prepends it to `PATH`, so the primary rule is: enter `nix develop` from the worktree being checked, and launch `claude` from that root (the agda-mcp registration in `.mcp.json` expands `${PWD}` at launch).

From a shell entered elsewhere, run this at the worktree root; the hook writes the worktree's wrapper (reproducing an existing one byte for byte) and the command prints its path as confirmation:

```
nix develop --command bash -c 'command -v agda'
```

Then type-check through it explicitly: `make AGDA=./.agda/bin/agda check` for the library and `./.agda/bin/agda src/Path/To/Module.lagda.md` for one module.  Without nix at hand, copy the main checkout's `.agda/` (gitignored) and rewrite the path:

```
WT=~/git/ualib/agda-algebras/worktrees/<branch>
M=~/git/ualib/agda-algebras/master
mkdir -p "$WT/.agda/bin"
sed "s#/agda-algebras/master/#/agda-algebras/worktrees/<branch>/#" "$M/.agda/libraries" > "$WT/.agda/libraries"
sed "s#/agda-algebras/master/#/agda-algebras/worktrees/<branch>/#" "$M/.agda/bin/agda" > "$WT/.agda/bin/agda"
chmod +x "$WT/.agda/bin/agda"
```

## Pre-PR gate: four targets, not one

`make check` is the type-check, and CI also runs three more gates: `make unused-imports` (fails on any unused import; a name used only in prose counts as unused), `make check-links` (the docs cross-links; run `make gen-links` first whenever a module was added or renamed, and commit the regenerated `docs/_links.md`), and `make docstrings` (the ADR-010 prose-block ratchet).  Run all four before opening a PR.
