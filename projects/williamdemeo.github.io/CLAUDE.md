# williamdemeo.github.io — working conventions

Personal website. Project conventions are yet to be written, and this
project's skills are yet to be extracted (the plan of record is a future
"skill extractor" pass over past session transcripts under
`~/.claude/projects/`).

## Layout and git

- `~/git/williamdemeo/williamdemeo.github.io/main` holds the main checkout;
  branch work goes in worktrees under
  `~/git/williamdemeo/williamdemeo.github.io/worktrees/`.

## Before pushing

CI runs two commands on every pull request, and both run locally in the dev
shell:

    nix flake check        # every generated-file check and the strict site build
    make check             # the same site build, through the Makefile

Run `nix flake check` before every push.  It takes about ten seconds when the
Nix store is warm and is exactly what CI runs.  It is the only thing that
catches a generated file left stale by an edit to the script that writes it,
which is the one mistake `make cv-pdf`, `make publications`, and the other
per-file targets cannot see.

Generated files that are committed, and the target that refreshes each:
`docs/assets/DeMeo-CV.pdf` (`make cv-pdf`, after any edit to `cv.yml` or
`cv/template.typ`); `cv/publications.typ`, `docs/publications.bib` and
`docs/_snippets/publications-*.md` (`make publications`, after any edit to
`bibliography.json` or `gen_publications.py`); `import/legacy-cv/inventory.tsv`
(`make cv-inventory`, only when a legacy extractor changes).  The CV page is
not a file: the site build renders it from `cv.yml` (ADR-010, revised
2026-09-10).

## Claude config for this project

Source of truth: the williamdemeo/claude-tooling repo
(projects/williamdemeo.github.io/), symlinked into place. Project skills
belong there, not in `~/.claude/skills/`.

PROBE-MARKER: claude-tooling/williamdemeo.github.io
