---
name: agda-typecheck
description: Typecheck Agda modules (.lagda.md / .agda) via the project's Nix flake. Use after editing any Agda module to verify it compiles, and before declaring Agda work done. Covers the `nix develop` invocation, reading common Agda errors, and the project's Agda quality gate.  One caveat: if the user launches claude from inside the Nix shell, then you can drop the `nix develop --command` prefix from each of the command instructions described below.
---

# Typechecking Agda in Nix-based repositories

Agda code in Nix-based projects (e.g., formal-ledger-specifications, agda-algebras, agda-native-air) typechecks only through its Nix flake (it pins the correct Agda version and Agda libraries).  There is no system-wide `agda` on `PATH`.  However, the `agda` command may be available if the user launches Claude Code from inside a Nix shell.

> Prerequisite: typechecking when the agent is launched outside a Nix shell requires `nix` to be available and the network policy to permit the flake's substituters (`cache.nixos.org` and `cache.iog.io`) and flake inputs (`github.com`).
> On Claude Code on the web, provision this with a SessionStart hook (see `.claude/hooks/`) and a network policy that allows those hosts; otherwise these commands will fail and Agda cannot be checked here.

## Procedure

1. Enter the toolchain. All Agda commands run inside the flake shell: `nix develop --command <cmd>`. (The flake pins the correct Agda version and the supporting Agda libraries we use.)
2. Check edited module(s) only — fast, and it localizes errors: `nix develop --command agda src/Path/To/Module.lagda.md`.
3. Do not stage generated artifacts (`*.agdai`, `Everything*.agda`, `/.agda/`); they are gitignored.

## Reading common Agda errors

+ Unsolved metas / yellow highlighting: a term's type is under-determined; add an explicit type signature or annotate the ambiguous argument.
+ `x != y of type T`: a definitional-equality mismatch; check whether the development expects setoid equality rather than propositional `_≡_`.
+ `No instance of ...`: a missing import, or an instance argument not in scope.

## Quality gate (verify before declaring done)

+ Every new public definition has an explicit type signature.
+ New lemmas are named, not inlined into opaque `rewrite` chains.
+ No `let` bindings are used if a `where` block *below* the proof could be used instead.
+ Helper functions and pattern matching are used instead of the `with` construction, unless the `with` substantially simplifies the presentation.
+ No new synonym was introduced for an existing concept.
+ Inline Agda names in prose use kramdown spans, e.g. `` `S`{.AgdaFunction} ``, `` `MySetoidModule`{.AgdaModule} ``.


