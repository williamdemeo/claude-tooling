---
name: scaffolding-a-module
description: Create a new Agda module in formal-ledger-specifications with the repo's literate conventions (frontmatter, --safe, hidden blocks, kramdown spans) and register it so it typechecks in the closure and gets a docs page. Use when adding a new module to fls.
---

# Creating a new fls module

Verified against `Ledger.Dijkstra.Specification.Leios.Abstract` and
`…Leios.Types` (2026-08-24).  The single best guide is a sibling module:
open the nearest one and mirror it before consulting anything generic.

## File shape (`src/…/<Name>.lagda.md`)

1. **Frontmatter** — every module starts with:

   ```
   ---
   source_branch: master
   source_path: src/Ledger/<Era>/.../<Name>.lagda.md
   ---
   ```

2. **One ATX H1** with an explicit anchor: `# Title {#sec:kebab-title}`.
   Subheadings are run-in italics on their own line (`*The vote*`), not ATX.

3. **Hidden vs visible code**.  The OPTIONS pragma, imports, module
   header, instance fields, and `derive-*` incantations go in
   `<!-- -->`-wrapped `agda` fences; the definitions readers care about go
   in visible fences.  State what the hidden blocks provide in one prose
   sentence (e.g. "All four types have decidable equality").

4. **Pragma and header**.  `{-# OPTIONS --safe #-}` only (NOT the
   `--cubical-compatible --exact-split` combination used in William's
   personal repos).  Imports come BEFORE the module header; parameter
   telescopes may open records inline:

   ```agda
   {-# OPTIONS --safe #-}

   open import Ledger.Prelude
   open import Ledger.Core.Specification.Epoch

   module Ledger.<Era>.Specification.<Name>
     (es : _) (open EpochStructure es using (Slot; DecEq-Slot))
     where
   ```

   Any instance a derivation or proof needs (e.g. `DecEq-Slot`) must be
   named in the `using` clause — opening only the type leaves the
   instance out of scope.

5. **Prose** — iterative-deepening, concise, kramdown spans for Agda
   names (`` `Vote`{.AgdaRecord} ``, `` `vSlot`{.AgdaField} ``,
   `` `hashEB`{.AgdaFunction} ``, `` `X`{.AgdaModule} ``).  Never repeat
   prose that exists in a sibling; reference it.  No status talk.

## DecEq

`Ledger.Prelude` exports the derivation tactic and the instances it
needs (including `DecEq-ℙ` from agda-sets, so `ℙ A` fields derive fine):

```agda
unquoteDecl DecEq-Vote = derive-DecEq ((quote Vote , DecEq-Vote) ∷ [])
```

## Registration (two places, both required)

- **Era aggregator** `src/Ledger/<Era>/Specification.lagda.md`: add a
  `## <Group>` heading (alphabetical order) with `import <FullName>`.
  A docs page exists iff the module is in the import closure of
  `src/Ledger.lagda.md`; the aggregator is what puts it there when no
  rule module imports it yet.
- **mkdocs nav** `build-tools/static/mkdocs/mkdocs.yml`: pages are
  listed EXPLICITLY; add `- <Leaf>: <Full.Dotted.Name>.md` in the
  matching nav group.  A nav entry without a generated page fails the
  strict site build (see the fls-mkdocs-site skill).

## Checking

From inside `nix develop` (drop the prefix only if already in it):

```
agda src/Ledger/<Era>/Specification/<Name>.lagda.md
agda src/Ledger/<Era>.lagda.md          # full-closure gate before push
```

Check agda's OWN exit code — a piped `agda … | tail` reports tail's.
