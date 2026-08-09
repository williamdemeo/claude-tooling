---
name: scaffolding-a-module
description: Create a new Agda module with the correct canonical path, literate .lagda.md structure, OPTIONS pragma, header, and documentation, ready to type-check. Use when adding a new module.
---

# Creating a new Agda module

## Literate structure

A module is `.lagda.md`: Markdown prose interleaved with Agda code fences, with inline Agda names written as kramdown spans, e.g. `` `S`{.AgdaFunction} ``, `` `MySetoidModule`{.AgdaModule} ``, `` `Semigroup`{.AgdaRecord} ``.  Lead with a prose statement of why the module exists and how it fits the development.  Write section headings as plain Markdown ATX headings (`### Title`); do not wrap them in HTML `<a id="…">…</a>` anchors — MkDocs slugifies heading text automatically.

## Skeleton

State the purpose in prose, then open the code block:

This module <one-line statement of purpose>.

```agda
{-# OPTIONS --cubical-compatible --exact-split --safe #-}

module <ParentModuleName>.<NewSubmoduleName> where

-- open import ...   -- canonical imports first

-- Definitions follow; give each an explicit type signature.
```

Continue with prose explaining each definition.

## Wiring and checking

Manually register the new module by importing it in a barrel module above it.

```agda
```agda
{-# OPTIONS --cubical-compatible --exact-split --safe #-}

module <ParentModuleName> where

open import <ParentModuleName>.<NewSubmoduleName> public 
```

+  Type-check per-file with either `agda src/Path/To/Module.lagda.md` or `nix develop --command agda src/Path/To/Module.lagda.md`.
+  Gate quality: explicit type signatures, small named lemmas, one canonical name per concept, prose paired with each formal statement.


