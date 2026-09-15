---
name: authoring-a-benchmark-obligation
description: Add a new proof obligation to the agda-native-air baseline benchmark (data/benchmarks/) — the paired obligation/gold Agda fixtures, the benchmark-index.jsonl entry, and the difficulty classification — ready to type-check. Use when curating or extending the M1-5 benchmark suite (Issue #13), and for retrieval-instrument rows (the haystack tier of #129, or a style-paired tier per #142) whose gold must be a shape the retrieval proposer can commit and whose exclusion gates must be re-run.
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

## Retrieval-instrument rows (the haystack tier, #129)

A row whose point is to measure retrieval (the needle is import-reachable but not `using`-listed and not the statement itself) has four extra rules, each learned from a ledger, and three gates.  All commands below were run on 2026-09-09/10.

+  **Shape**.  The gold is ONE lemma applied to goal-context NAMES, with at most three visible binders in the lemma's lane-printed telescope (hypotheses count as visible), because `Retrieve.scala`'s `shapes` saturates every visible binder over context names (arity ≤ 3, ≤ 27 tuples) and `fill_hole` refuses candidates with unsolved metas.  `+-cancelˡ-≡` (four visible binders) and `trans`-composites are unreachable; so is a Π-typed goal, since a hypothesis left in the goal needs a partial application — bind every hypothesis in the clause (`foo m eq = {!!}`).
+  **Statement**.  Not a library lemma up to renaming, and not one after `_<_`/`_≥_`/alias families unfold (the lane-form exclusion compares normalized printings).  Use diagonal instances (`+-suc m m`), hypothesis-consuming instances (`+-mono-≤ le le`), or unification-solved implicits (`length-++ xs`).
+  **Imports**.  Open the haystack with a narrow `using` list of one or two decoys (same family, cannot close the goal in term mode); write the gold with the needle QUALIFIED (`Data.Nat.Properties.+-suc m m`, the text the retrieval ladder renders).  Put the statement's type formers in the Base import: a name not in scope prints qualified in the goal display (`ℕ.suc`, `Data.Nat.Base.≤`) and the scorer never dequalifies goal tokens.
+  **Index**.  `source` stays the library (`agda-stdlib`), `tags` carry `stratum:haystack`, `proofStrategy` is `application`, and the id prefix names the tier (`haystack-…`).

The three gates, from the repo root inside `nix develop .#backend` (build the server once with `cd agda-mcp && cabal build exe:agda-mcp`, then `BIN=$(cd agda-mcp && cabal list-bin exe:agda-mcp)`; the stdlib v0 corpus must be staged at `data/corpora/agda-stdlib/v0/corpus.jsonl`):

```sh
python3 scripts/python/corpus/check_haystack_exclusion.py --corpus data/corpora/agda-stdlib/v0/corpus.jsonl --index data/benchmarks/benchmark-index.jsonl --tag stratum:haystack
make proof-search-loop PROOF_SEARCH_PROPOSER=fixed     PROOF_SEARCH_LOOP_IDS="--ids id1,id2" PROOF_SEARCH_RUN_ID=<run> AGDA_MCP_BIN=$BIN
make proof-search-loop PROOF_SEARCH_PROPOSER=retrieval PROOF_SEARCH_CORPUS=data/corpora/agda-stdlib/v0/corpus.jsonl PROOF_SEARCH_LOOP_IDS="--ids id1,id2" PROOF_SEARCH_RUN_ID=<run> AGDA_MCP_BIN=$BIN
```

Pass: the checker exits 0; every fixed-space status is `exhausted` or `budget_exceeded`; in the retrieval `report.json`, every outcome's `retrieval.excluded` is empty.  Read `retrieval.proposedLemmas` for whether the needle reached the cut (a null there is a valid instrument, not a defective fixture), and `results.jsonl` for whether its shapes were probed at all (a needle at rank 1 with no probe means the peek rejected it; confirm by driving `type_of` and `fill_hole` on the run's `work/` copy per the `driving-agda-mcp` skill).  Serialize sweeps: two sbt runs in one checkout conflict.
