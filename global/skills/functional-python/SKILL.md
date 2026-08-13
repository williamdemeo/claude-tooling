---
name: functional-python
description: William's house style for ALL Python work in his projects — functional programming is an insistence, not a preference. Use whenever writing, reviewing, or refactoring any Python in agda-native-air, agda-algebras, williamdemeo.github.io, github-project, or any repo with a scripts/python/ tree. Covers total functions with Result (never exceptions for control flow), the homegrown utils/_utils API (use it, never reimplement it), layout (all Python under scripts/python/, tests, a Makefile target per suite), type annotations everywhere, and the File-header documentation convention.
---

# Functional Python, the house style

Every rule here is enforced taste, not a suggestion. When existing code in
the project conflicts with this skill, match the project and flag the
conflict; when writing new code, this skill wins.

## The rules

1. **Functional by default**: total functions, structural recursion, no
   hidden effects. Pure core, effectful shell: parsing, I/O, subprocess,
   and `sys.exit` live at the edges; everything between is pure functions
   over immutable data.
2. **All Python lives under `scripts/python/`** — one subdirectory per
   tool family (e.g. agda-algebras has `scripts/python/flrp/`), singletons
   at the top level. Never create sibling script trees elsewhere in the
   repo. Every suite gets a Makefile target.
3. **Utils first**: before writing any helper, read the project's utils
   package — `scripts/python/utils/` (agda-native-air) or
   `scripts/python/_utils/` (agda-algebras, williamdemeo.github.io). Never
   reproduce functionality that exists there; a genuinely general new
   helper goes INTO that package, not beside your script.
4. **Test the code.** Match the project's existing test layout:
   agda-native-air keeps tests in `scripts/python/tests/`; agda-algebras
   and williamdemeo.github.io keep `test_<module>.py` beside the module
   (including inside family dirs). New projects default to
   `scripts/python/tests/`. Pure functions are tested directly, no mocks.
5. **Document liberally.** Every file opens with the docstring header
   below; every section whose "why" is not obvious gets a why-comment.

## The utils API (read the local copy; air's is the upstream and has drifted)

`pipeline_types` is the core — functional error handling and immutable
state, all `@dataclass(frozen=True)`:

- `Result[T, E]`: `Result.ok(v)` / `Result.err(e)`, predicates
  `is_ok()` / `is_err()`, eliminators `unwrap()` / `unwrap_or(default)` /
  `unwrap_err()`, and the combinators that replace try/except control
  flow: `map(f)`, `map_err(f)`, `and_then(f)` (alias `flat_map`) for
  chaining `T -> Result[B, E]`.
- `PipelineError` (with `ErrorType` enum and `.with_context(**kwargs)`)
  is the standard error payload.
- `sequence_results(...)` and `collect_errors(...)` traverse a list of
  Results (all-or-nothing vs partition).
- Immutable state with persistent updates that RETURN NEW VALUES:
  `PipelineState.add_file(...)`, `PipelineStatistics.add_error()`,
  `FileMetadata.advanced_to(stage)` — never mutate, always rebind.

`file_ops` wraps the filesystem in Results — `read_text`, `write_text`,
`load_json`, `write_json`, `ls_dir`, `cp_file`, `cp_dir`, `rm_artifact`,
`ensure_dir_exists`, … all return `Result[..., PipelineError]`. Do not
call `open()` or `shutil` directly in pipeline code. `command_runner.
run_command` wraps subprocess the same way (`CommandResult.success`).
`text_processing` holds pure text transforms (`slugify`, admonition and
cross-ref processing).

## Style specifics

- **Errors are values.** A function that can fail returns
  `Result[T, PipelineError]`; `raise` is reserved for genuine bugs
  (assertion-class violations), never for expected failure paths. Chain
  with `and_then`, not nested ifs:

  ```python
  def publication_count(path: Path) -> Result[int, PipelineError]:
      """Count entries in a publications JSON file."""
      return load_json(path).map(lambda data: len(data.get("entries", [])))
  ```

- **Type-annotate everything** — parameters, returns, module-level
  constants. `from __future__ import annotations` at the top.
- **Immutability**: `@dataclass(frozen=True)` for domain types; tuples
  over lists for fixed shapes; never mutate an argument; "updates" return
  new values (see the persistent-update methods above).
- **Comprehensions, generator expressions, or recursion over imperative
  loops**; if a loop accumulates, ask whether it is a comprehension,
  `functools.reduce`, or `sequence_results` in disguise.
- **Small named functions** with one job; a pipeline reads as a chain of
  named stages, not a page of statements.
- **CLI shells**: `argparse`/`sys.argv` handling in `main()` only;
  `main()` converts a final `Result` into an exit code and messages;
  nothing below `main()` prints or exits.

## The documentation header

Every file starts with this shape (real example from the codebase):

```python
"""
File: scripts/python/_utils/pipeline_types.py

Description: Types for the documentation build pipeline.

  This module provides functional programming primitives and immutable
  data structures that make the pipeline more functional, robust, and
  predictable.
"""
```

`File:` is the path relative to the repo root — always. Add
`Design Principles:` or `Provenance:` sections when they earn their place.
Inside the code, comment the WHY wherever a reader would ask it; do not
narrate the WHAT.

## Review checklist (apply to any Python diff)

Unannotated def · try/except steering control flow · direct `open`/
`shutil`/`subprocess` where `file_ops`/`command_runner` exists · mutation
of arguments or shared state · a helper that duplicates the utils API ·
code outside `scripts/python/` · a file without the `File:` header ·
logic in `main()` beyond argument parsing and Result elimination · new
code without a test · a suite without a Makefile target.
