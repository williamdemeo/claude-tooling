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

4.  Wire the engine.  Flake-repo targets (primary, verified on agda-native-air): add the input `github-project.url = "github:williamdemeo/github-project";`, re-export its apps under a prefix, and call them from make — a `flake.lock` entry then pins the engine and `nix flake update github-project` upgrades it deliberately.

    ```nix
    apps = nixpkgs.lib.genAttrs systems (system:
      nixpkgs.lib.mapAttrs'
        (name: app: nixpkgs.lib.nameValuePair "ghproject-${name}" app)
        github-project.apps.${system});
    ```

    ```make
    GHPROJECT_DIR ?=
    ifneq (,$(GHPROJECT_DIR))
    GHPROJECT_LINT := python3 "$(GHPROJECT_DIR)/scripts/gh_project_lint.py"
    else
    # `\#`: an unescaped # starts a comment even inside an assignment.
    GHPROJECT_LINT := nix run .\#ghproject-lint --
    endif

    project-lint:
    	$(GHPROJECT_LINT) docs/GITHUB_PROJECT.md
    ```

    (update / update-check follow the same shape; keep `GHPROJECT_DIR` as the checkout escape hatch for engine development and Nix-less machines.)  For a repo without a flake, the checkout shape alone — `GHPROJECT_DIR ?= $(HOME)/git/williamdemeo/github-project/main` with a `test -f` guard — still works; the engine is stdlib-only Python.  A fresh non-adoption project created FROM the template instead runs its `make init`, which wires all of this automatically.

5.  Retire the old order: delete any vendored roadmap scripts, freeze the legacy plan file (banner at top declaring it historical and pointing at `GITHUB_PROJECT.md`), and repoint live-status cross-references (README, CONTRIBUTING, issue templates, architecture docs).

## Gotchas

+  A mirrored issue body inside a generated region may itself mention retired files or contain marker-like text; leave it alone — regions are GitHub-owned and the engine defangs markers itself.
+  `update` exit codes: 0 current/written, 1 stale (`--check` only), 2 the run failed — distinguish "stale" from "broken" in automation.
+  Bodies render on GitHub AND in the file, so plan-file prose conventions (the `+` bullet style) apply only to hand-written sections; generated content is verbatim GitHub.

## Authoring a FRESH plan (no issues on GitHub yet)

The adoption flow above assumes issues already live on GitHub.  For a
brand-new plan (verified on the formal-ledger-specifications fork,
2026-08-18), five things differ:

1.  Author the issues INSIDE the `BEGIN/END GENERATED: milestone-N`
    marker pairs — for a fresh plan they are populate's input
    (`### Issue MN-k: Title`, a `**Labels:**` line, a
    `**Milestone:** N. Title` line, body, `---` separators), exactly as
    in the template's worked example.  Empty marker pairs are for
    adoption only.
2.  Before the first populate, run ONLY the lint (offline, safe).
    NEVER run gh_project_update.py first: update rebuilds regions FROM
    GitHub, which for a fresh plan means erasing every authored issue
    body.
3.  Reuse the target repo's existing topic labels EXACTLY — name and
    color from `gh label list -R OWNER/REPO --limit 100` — so populate
    matches them as existing instead of reporting collisions; only the
    `milestone-N-*` labels should be new.  Description differences are
    reported but never overwritten, which is harmless.
4.  Populate creates `N. Title` milestones and one issue per heading on
    the target repo.  On a shared org repo that is the owner's call:
    get explicit approval before running populate, and check the repo's
    existing milestone-title scheme (e.g. fls uses `May - Jul`) for
    coexistence questions worth raising first.
5.  AFTER the first populate, run gh_project_update.py once WITHOUT
    --check and commit the rewrite: the canonical rendering differs
    cosmetically from authored input (drops each issue's
    `**Milestone:**` line, re-orders labels to GitHub's order, trims
    the trailing `---` separators; bodies untouched — verified in the
    wild 2026-08-18).  A --check straight after populate reports stale
    BY DESIGN (exit 1 = stale, not broken); after the normalization
    commit, --check exits 0 and becomes the ongoing drift gate.
