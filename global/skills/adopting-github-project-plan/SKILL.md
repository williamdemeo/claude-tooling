---
name: adopting-github-project-plan
description: Adopt an EXISTING repository (issues already live on GitHub) onto the williamdemeo/github-project plan-file model — author docs/GITHUB_PROJECT.md, fill its generated regions with the engine, repair title-id defects lint surfaces, and wire thin Makefile targets so the engine is referenced, never vendored.  Use whenever a repo with live issues should gain a GITHUB_PROJECT.md synced to GitHub, or when retiring a stale vendored copy of the roadmap scripts.  First done for agda-native-air (its issue #92).
---

# Adopting an existing repo onto the github-project plan model

The engine lives in `~/git/williamdemeo/github-project/main/scripts/` (`gh_project_populate.py`, `gh_project_update.py`, `gh_project_lint.py`); it is stdlib-only Python, so plain `python3` runs it.  Never copy it into the target repo — that is the drift this skill exists to end.

## How the engine decides what renders

+  `update` rebuilds only regions between `<!-- BEGIN GENERATED: milestone-N -->` / `<!-- END GENERATED: milestone-N -->`; everything outside is preserved byte-for-byte.
+  Only issues whose GitHub title starts with a parseable `[MN-k]` or `[MN-ka]` prefix (regex `M(\d+)-(\d+)([a-z]?)`) render; dotted forms like `[M0-10.1]` do NOT parse and are silently excluded, as are unprefixed issues.
+  Milestone assignment order: `milestone-N-*` label → leading integer of the GitHub milestone title (`N. Title` format) → the `[MN-k]` prefix's N.  A repo whose milestones are titled `0. Foo`, `1. Bar` therefore adopts with zero GitHub mutations.

## Procedure (verified on agda-native-air, 2026-08-16)

1.  Author `docs/GITHUB_PROJECT.md` from the template's worked example (`~/git/williamdemeo/github-project/main/docs/GITHUB_PROJECT.md`): header comment, `**Repository**:  \`owner/repo\``, Summary, Labels (`- \`name\` (color) — description.`), `### Milestone N — Title` entries with Description and Exit criterion, a hand-authored mermaid dependency graph, then per-milestone `## Milestone N — Title` sections each containing an EMPTY marker pair.  Add a hand-written "Field-driven work outside the milestone plan" section linking tracking issues that lack `[MN-k]` prefixes — the engine cannot render those.
2.  Lint offline, then fill and verify idempotence:

    ```sh
    python3 ~/git/williamdemeo/github-project/main/scripts/gh_project_lint.py docs/GITHUB_PROJECT.md
    python3 ~/git/williamdemeo/github-project/main/scripts/gh_project_update.py docs/GITHUB_PROJECT.md
    python3 ~/git/williamdemeo/github-project/main/scripts/gh_project_update.py docs/GITHUB_PROJECT.md --check
    ```

3.  Repair what lint surfaces, on GitHub, not in the file: duplicate ids (`duplicate issue ID MN-k`) — retitle the LATER-created issue to the next free ordinal; dotted sub-issue ids — retitle to the letter-suffix form the engine parses (`[M0-10.1]` → `[M0-10a]`).  Retitling closed issues is low-risk; re-run update after each repair.

    ```sh
    gh issue list --repo OWNER/REPO --state all --search "M0- in:title" --json number,title
    gh issue edit N --repo OWNER/REPO --title "[M0-11] ..."
    ```

4.  Wire thin Makefile targets that call the engine from a checkout (until github-project ships a Nix flake package; then switch to a pinned flake input):

    ```make
    GHPROJECT_DIR ?= $(HOME)/git/williamdemeo/github-project/main

    _check-ghproject:
    	@test -f "$(GHPROJECT_DIR)/scripts/gh_project_update.py" || { \
    	  echo "error: github-project engine not found at $(GHPROJECT_DIR)"; exit 1; }

    project-lint: _check-ghproject
    	python3 "$(GHPROJECT_DIR)/scripts/gh_project_lint.py" docs/GITHUB_PROJECT.md
    project-update: _check-ghproject
    	python3 "$(GHPROJECT_DIR)/scripts/gh_project_update.py" docs/GITHUB_PROJECT.md
    project-update-check: _check-ghproject
    	python3 "$(GHPROJECT_DIR)/scripts/gh_project_update.py" docs/GITHUB_PROJECT.md --check
    ```

5.  Retire the old order: delete any vendored roadmap scripts, freeze the legacy plan file (banner at top declaring it historical and pointing at `GITHUB_PROJECT.md`), and repoint live-status cross-references (README, CONTRIBUTING, issue templates, architecture docs).

## Gotchas

+  A mirrored issue body inside a generated region may itself mention retired files or contain marker-like text; leave it alone — regions are GitHub-owned and the engine defangs markers itself.
+  `update` exit codes: 0 current/written, 1 stale (`--check` only), 2 the run failed — distinguish "stale" from "broken" in automation.
+  Bodies render on GitHub AND in the file, so plan-file prose conventions (the `+` bullet style) apply only to hand-written sections; generated content is verbatim GitHub.
