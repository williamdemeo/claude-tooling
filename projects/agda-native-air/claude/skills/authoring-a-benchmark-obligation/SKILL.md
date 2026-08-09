---
name: authoring-a-benchmark-obligation
description: Add a new proof obligation to the agda-native-air baseline benchmark (data/benchmarks/) — the paired obligation/gold Agda fixtures, the benchmark-index.jsonl entry, and the difficulty classification — ready to type-check. Use when curating or extending the M1-5 benchmark suite (Issue #13).
---

# Authoring a benchmark obligation (M1-5)

A benchmark entry is three things kept in sync: an **obligation** file with a hole, a **gold** file that fills it, and an **index** line that describes both.

## 1. Choose and classify

+  Pick an obligation with a stable module path, a clear hole identifier, and a known gold solution.  Classify it into a tier using `docs/benchmarks/taxonomy.md`: `routine` (Tier 1), `compositional` (Tier 2), or `non-obvious` (Tier 3).
+  Keep the gold the simplest correct term a reader would write, not a minimal-token golf — readability matters for the corpus.

## 2. Write the fixtures

Two files with the **same module name** (matching the file stem):

+  `data/benchmarks/<lib>-v0/obligations/<Name>.agda` — the statement with exactly one `{!!}` hole.
+  `data/benchmarks/<lib>-v0/gold/<Name>.agda` — identical, but the hole is replaced by the gold term.

Each file opens with a short comment header (filename, obligation id, difficulty, source module, strategy), then `open import AgdaDojang.Debug`, then the minimal stdlib imports needed.  Provide prerequisite lemmas via explicit imports — the obligation may import lemmas, just not the definition it is asked to prove.  Mirror the existing fixtures `Nat-plus-identityL.agda` (Tier 1, `refl`) and `Nat-plus-comm.agda` (Tier 2, induction + `≡-Reasoning`).

## 3. Add the index line

Append one JSON object to `data/benchmarks/benchmark-index.jsonl` with the fields documented in `data/benchmarks/README.md`: `id`, `source`, `module`, `obligation`, `gold`, `goldTerm`, `hole`, `type`, `difficulty`, `domain`, `proofStrategy`, `tags`.  The `obligation` and `gold` paths are relative to the repo root.

## 4. Type-check the gold

Verify before committing (see the `typechecking-agda` skill): `nix develop .#backend --command agda data/benchmarks/<lib>-v0/gold/<Name>.agda`.

The gold must type-check with no errors or unsolved metas.  The obligation file, with its hole, is expected to report an interaction point — that is fine.

## Gate

+  Obligation and gold share a module name and differ only at the hole.
+  The `benchmark-index.jsonl` line, the files on disk, and the difficulty tier agree.
+  `agda-stdlib` obligations check with no extra setup; `agda-algebras` obligations require `AGDA_ALGEBRAS_ROOT` set before entering the shell.
