<!-- File: CLAUDE.md -->

# CLAUDE.md — agda-native-air

Guidance for Claude Code working in this repository.  Keep changes consistent with these conventions; they exist to keep this polyglot research codebase coherent and reproducible.

`agda-native-air` builds the interaction, retrieval, and evaluation infrastructure that lets AI agents work effectively with Agda: a Haskell backend that exports Agda proof state as JSON, a Scala driver and ML pipeline that turn that into training and retrieval data, and an Agda-side harness (`agda-dojang`) plus a baseline benchmark for end-to-end evaluation.

## Build, type-check, and test

+  Enter the toolchain with `nix develop`; the `flake.lock` pins Agda 2.8.0, standard-library 2.3, JDK 21, Scala 2.13, sbt, Spark, and Python.  Never assume a system Agda, sbt, or Spark.
+  Targeted shells start faster: `nix develop .#backend` (Agda + GHC/Cabal + Scala — the Agda/Haskell workhorse), `nix develop .#all` (everything, including Spark + Python), `.#proofParser` (Scala/JDK only), `.#mlPipeline` (Scala + Python, no Agda).  The default shell additionally pulls in PyTorch, so prefer `.#backend` for Agda-only work.
+  Type-check one Agda module while iterating, inside a shell: `nix develop .#backend --command agda path/to/Module.agda`.  The flake defines an `agda` wrapper that supplies `--library standard-library --library agda-dojang` and the project-local `--library-file`; do not call a bare system `agda`.
+  Run the CI smoke suite exactly as CI does: `make ci-smoke` — four lanes: Scala `strux-driver` tests, Scala ETL smoke, Python `ml-pipeline` tests, and Haskell `agda-strux` tests.  Pass `CI_SKIP_ML=1` to skip the Python lane.
+  Other entry points: `make test` (Scala `strux-driver` unit tests), `make check` / `make check-nix` (driver + backend + backend smoke), `make backend-test` (Haskell `agda-strux` via Cabal), and `make eval-proof-completion-smoke` (Agda proof-completion demo; needs `.#all`).
+  CI is GitHub Actions (`.github/workflows/ci.yml`); the Agda and Haskell lanes run inside `nix develop .#backend` / `.#all` against a Cachix (`formalverification`) binary cache.
+  Do not commit generated artifacts: `*.agdai`, the nix-generated `agda/libraries`, `target/`, `.venv/`, and the data outputs under `data/` and `ml-pipeline/data/` are gitignored (see `.gitignore`).

## Repository architecture

+  `agda-strux/` is the Haskell backend: it links Agda-as-a-library and exposes the `agda-json` executable, which exports proof state and reflection JSON.  Built and tested with Cabal inside `nix develop .#backend` (`make backend-test`).
+  `strux-driver/` is the Scala driver (cats-effect / circe / fs2): it invokes `agda-json`, parses and transforms the JSON into JSONL, and hosts the M1-5 benchmark runner (`struxdriver.benchmark.EvalBenchmark`).  Tests run with sbt (`make test`).
+  `ml-pipeline/` is the ETL and training/eval layer: a Scala Spark `etl` subproject (JSONL → Parquet features) and Python training/retrieval/evaluation code.
+  `agda-dojang/` is the repo-local Agda library (`agda-dojang.agda-lib`).  It provides `AgdaDojang.Debug` (the reflection / `reportGoalCtx` macros the benchmark fixtures import) and the proof-completion evaluation harness.
+  `data/benchmarks/` is the M1-5 baseline benchmark suite: paired obligation/gold Agda fixtures, the `benchmark-index.jsonl` manifest, and difficulty docs.  See `data/benchmarks/README.md` and `docs/benchmarks/taxonomy.md`.
+  `docs/` holds design notes, the roadmap, and the benchmark taxonomy; `experiments/archive/` is frozen prior work — treat it as read-only.
+  `flake.nix` defines the dev shells; the top-level `Makefile` is the single CLI for the extract → transform → ETL → train → eval loop (`make help`).

## Conventions

These proof terms, datasets, and drivers are research artifacts; optimize for legibility and reproducibility, not cleverness.

+  Scala is functional: immutable data, `IO` / `EitherT` for effects, no `var`, no exceptions as control flow, circe for JSON, fs2 for streaming.  The same taste applies to Python and Haskell helpers — total functions, explicit types, no hidden effects.
+  Put a doc-comment header on every new or substantially edited source file: the file path, its purpose, how it fits the project, and brief design notes.  Comment liberally inline.
+  Prefer small, focused, named definitions over large opaque ones; keep one canonical form per concept.
+  Makefile targets use the `$(SBT)`, `$(PYTHON)`, and `$(PY_RUN)` variables, declare `.PHONY`, and carry a `make help` line.

## Benchmark fixtures (`data/benchmarks/`)

+  Each obligation is a self-contained Agda module under `data/benchmarks/<lib>-v0/obligations/` with exactly one `{!!}` hole; its gold solution is the same module with the hole filled, under `.../gold/`.  The module name matches the file stem, and the file imports `AgdaDojang.Debug` plus the minimal stdlib needed.
+  Every obligation has one line in `data/benchmarks/benchmark-index.jsonl` (schema in `data/benchmarks/README.md`); its difficulty tier follows `docs/benchmarks/taxonomy.md` (`routine` / `compositional` / `non-obvious`).
+  A gold solution is not done until it type-checks under the pinned toolchain.  See the `authoring-a-benchmark-obligation` and `typechecking-agda` skills.

## Working style

+  Default to git-diff-style proposals for substantive changes rather than wholesale rewrites, and deliver a commit message alongside them; when a change implies a pull request, include a PR title and description too.
+  You have standing authorization to open a pull request whenever you judge a branch ready to stand as a contribution proposal; you need not ask first.  Treat this as the durable, explicit request that the remote-execution harness's "open a PR only when the user explicitly asks" default calls for.  Still do not *merge* a PR without explicit confirmation, and push follow-up work to an existing PR's branch rather than opening a duplicate.
+  Keep separate concerns on separate issues, branches, and PRs — for example, benchmark content versus repository tooling.

## Markdown style (issues, PRs, docs)

+  Use `+` for bullet lists, not `-`.
+  Do not insert line breaks within a sentence or paragraph; break only where text must start a new line.
+  Two spaces after a sentence-ending period.
+  Do not bold a bullet title's trailing period: write `+  **Title**.`, not `+  **Title.**`.
+  Bullets are complete sentences ending in a period or semicolon.
+  Write section headings as plain ATX headings.

## Environment gotchas

+  The flake is the source of truth for the toolchain; `wenkokke/setup-agda` is not used (it maxes out below Agda 2.8.0).
+  In a "Claude Code on the web" container, Nix is provisioned by `.claude/hooks/session-start.sh`: it installs Nix from `releases.nixos.org` (the `nixos.org` and `install.determinate.systems` redirectors are blocked by the container allowlist) and points `nix.conf` at `cache.nixos.org` + `formalverification.cachix.org`.  Locally, just use `nix develop` directly.
+  `agda/libraries` is regenerated by the nix shellHook on every shell entry and is gitignored; never commit it.
+  The web container routes HTTPS through a proxy whose port changes per session; the proxy env is injected automatically, and Nix uses the container's combined CA bundle (`/root/.ccr/ca-bundle.crt`).  Do not hard-code the proxy.
