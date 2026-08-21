---
name: extracting-a-library-corpus
description: Run agda-native-air's extract → assemble pipeline over a whole Agda library and package the result as a publishable corpus with coverage, provenance, statistics, and a dataset card. Use when extracting any library at scale (agda-algebras, the standard library, agda-categories, TypeTopology), when a corpus needs regenerating at a new library commit, or when an extraction run has to be reported honestly rather than just re-run.
---

# Extracting a library corpus in agda-native-air

Getting a corpus is four steps and one habit.  The habit: the failures list is a deliverable, so never summarize a run you have not read the manifest of.

## The sequence

Run from the repo root, from a plain shell.  The `-nix` targets enter the right dev shell themselves.

```sh
# 1. Module list + Agda's own dependency graph.  Typechecks the whole library.
make extract-lib-nix AGDA_ALGEBRAS_ROOT=<clean-checkout> PAR=8 RESUME=0

# 2. Package it: corpus.jsonl(.gz), coverage.json, provenance.json, stats.{json,md}
make corpus-nix

# 3. Prove the consumer can use it, over the real JSON-RPC transport.
make corpus-mcp-smoke
```

Step 1 runs `agda-algebras-metadata` as a prerequisite, so the module list and the DOT graph come for free; `make corpus-stats` reads that DOT for module-level import shape.

## Choices that matter

+  **`RESUME=0` for a corpus you will publish.**  Resume decides by validating the existing per-module JSONL, and an empty file validates — which is correct for the ~15% of modules that are barrels, and indistinguishable from a module that failed and left a zero-byte output.  A from-scratch run cannot be confused this way, and its manifest says `resume: false`.
+  **`PAR=8` is a reasonable default** on a 20-core machine.  Each module is a separate `agda-json` process linking Agda-as-a-library.
+  **Warm `_build` matters more than parallelism.**  agda-algebras' 375 modules took 5.5 minutes wall (7,055 s of module time) with interfaces already built in the library's own `_build/`; from cold, expect much longer.  Interfaces land in the *library's* `_build/`, which its `.gitignore` covers, so the source checkout stays clean.
+  **Commit before the final assembly.**  `provenance.json` records `workingTreeDirty` for both the library and this repo.  A corpus whose provenance says the producer was dirty is not reproducible, so: commit, then re-run `make corpus-nix` (about 30 s) and use those digests.
+  **Determinism is checkable.**  Two assembly runs over the same extraction must produce identical `sha256` for both `corpus.jsonl` and `corpus.jsonl.gz`.  Verify it rather than asserting it; it is one command and it is what makes the digests in the card mean anything.

## Reading the outcome

`data/<lib>/raw/run-manifest.json` carries a `summary` and one `results` record per module.  Start there, not in the log:

```sh
python3 -c "
import json; m=json.load(open('data/agda-algebras/raw/run-manifest.json'))
print(m['summary'])
print([r['module'] for r in m['results'] if not r['ok']])
"
```

A failure's `validateErrors` and `logFile` name the cause.  The per-module log opens with a `REPRO:` line — the exact `agda-json` invocation with its `AGDA_DIR` — so reproducing one failure is a copy-paste, not a reconstruction.

Two classes of "failure" are not extractor bugs, and a card should say so:

+  **Zero-row successes** are barrel modules (`Classical`, `Overture`, `EverythingLegacy`, …): `import` lines only, so nothing of their own to extract.  59 of agda-algebras' 375.
+  **Files that are not modules** never enter the module list.  A literate front page with no `module` declaration, or one whose stem is not a valid Agda identifier (`agda-algebras.lagda.md`), is filtered by the metadata scanner, which also reserves the name `Everything` for its own synthetic root.

## Statistics and the card

`make corpus-stats` writes `stats.json` plus `stats.md` tables.  Numbers worth pulling out for a card, because a reader will otherwise assume the opposite:

+  **Rows vs. distinct `prettyQname`.**  Normalization drops anonymous module segments, so names collide; consumers keyed on `prettyQname` (agda-mcp keeps the last) index fewer rows than the file has.  Report both.
+  **Edges leaving the corpus vs. staying inside.**  A library corpus is not a closed graph — three of five type-level references in agda-algebras point at the standard library or `Agda.Primitive`.
+  **Byte concentration.**  A handful of machine-generated certificate proofs can be a fifth of the corpus.  Check the largest rows before quoting an average.

## Sanity checks that have each caught a real defect

+  Does the module count match the source-file count, minus the files you can name a reason for?  A count that is *far* short means source resolution, not Agda.
+  Are the dependency tokens qualified or bare?  A real extraction prints Agda's internal names, so they are fully qualified.  Consumers written against a small hand-made fixture tend to assume bare names and then silently resolve nothing.
+  Does `agda-mcp --corpus <the real corpus>` load at a footprint you would accept?  Measure it: `/usr/bin/time -v "$BIN" --corpus … < one-tools-list-request.jsonl`.
