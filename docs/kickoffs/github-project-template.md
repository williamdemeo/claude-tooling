<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-1-github-project-template.md
     (revised 2026-08-13 to fold in the website-lineage scripts, issue #293,
     and the vendored-utils decision). Launch a fresh session with:
     Read and execute `~/claude-kickoff-prompts/kickoff-1-github-project-template.md` -->

# Kick-off: build out the `github-project` template repository

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt and the referenced paths. Where a
decision belongs to William, ask instead of assuming. Push back where his
ideas seem misguided — he explicitly wants that.

## Mission (why this repo exists)

Three of William's projects run GitHub-project roadmaps from near-copies of
the same populate/update scripts, and the copies have drifted apart:
improvements land in one project and are forgotten by the others, and a
known-issues list (ualib/agda-algebras#293) sat unaddressed while the same
buggy code was copied onward. This repository ends that: it distills the
best of everything learned about GitHub project creation and tracking into
ONE canonical, public template that future projects start from and existing
projects re-vendor from. Slogan: "a template for creating and working on
GitHub projects, especially (though not exclusively) useful for AI-assisted
projects."

## Where you are

The repository already exists but is an empty stub (one commit, README
only): `williamdemeo/github-project` (PUBLIC, intended as a GitHub
*template repository* — verify the toggle:
`gh api repos/williamdemeo/github-project --jq .is_template`, and ask
William before flipping it). You are on `main`, checked out at
`~/git/williamdemeo/github-project/main`. Convention: `main` stays checked
out there; dev branches live in git worktrees under
`~/git/williamdemeo/github-project/worktrees/<branch>`. William reviews and
merges his own PRs, so the cycle is fast — but still work in branches/PRs,
not directly on main, once the skeleton exists.

A LICENSE is needed (public template) — recommend MIT or Apache-2.0; ask.

## Source material (read all of it before designing)

The script lineages, and how they relate (measured 2026-08-13):

| file | agda-algebras (`master/scripts/python/`) | williamdemeo.github.io (`main/scripts/python/`) | agda-native-air |
|---|---|---|---|
| `gh_project_populate.py` | 2026-04-26 lineage | **2026-07-29 — newest** | 2026-03-13, standalone, no lib/utils |
| `gh_project_render.py` | 2026-05-04 lineage | **2026-07-31 — newest** | absent |
| `_gh_project_lib.py` | identical | identical | absent |

- **The website's copies are the primary ancestor** (newest: title-prefix
  normalization in populate; drift-vs-failure separation and
  `--no-env-prefix` in render). The agda-algebras copies carry distinct
  earlier fixes (created-vs-already-existed tally in populate;
  `[MN-ka]` alphabetic-suffix issue IDs in render) — DIFF the pairs and
  take the UNION; do not assume either side subsumes the other. Air's
  standalone populate is the reference for what a no-dependencies variant
  looks like.
- `docs/GITHUB_PROJECT.md` exemplars: agda-algebras' (the original: labels
  section, milestones with exit criteria, mermaid dependency graphs,
  `BEGIN/END GENERATED` markers) and the website's (driven by the newest
  scripts; see its Makefile's `RENDER` target for real invocation flags).
- `~/git/IO/fls/master/build-tools/scripts/` and
  `~/git/IO/fls/master/docs/adr/0001-ledger-property-tracking.md` — a
  sibling system. Do NOT copy its catalog/derived-status design (that works
  only when "done" is machine-checkable); DO steal its hardening and its
  ADR style (the one-source-of-truth-per-concern table).
- **ualib/agda-algebras#293** ("Follow-up to #289 — known issues in the
  gh_project tooling") — read it in full; its six items are requirements
  here (next section).
- The scripts consume the shared functional-Python package
  (`_utils`/`utils`: `Result`, `file_ops`, `command_runner`) — identical
  across all three projects as of 2026-08-13 (air PR #91). All Python work
  follows the `functional-python` skill in your skills list; it documents
  this API.

## Known issues to fix here (from #293 — do not re-forget them)

Five live in the shared utils package (fix them in whatever this template
vendors; they are NOT yet fixed in the three projects):

1. `Result.unwrap()` rejects `Ok(None)` — the success extraction keys on
   `_value is not None`, but `Result.ok(None)` is legal and common
   (`file_ops.write_text` returns `Result[None, _]`). Key solely off
   `_is_ok`.
2. `Result.map()` catches exceptions and synthesizes `Result.err(e)` of the
   wrong error type. Either let exceptions propagate or wrap in
   `PipelineError(ErrorType.VALIDATION_ERROR, …)`.
3. `file_ops.calculate_file_metadata` annotates `stage: ProcessingStage`
   without importing it (hidden by postponed evaluation).
4. `command_runner` with `stream_output=True` can deadlock (stdout drained
   to completion before stderr; thread the readers or merge via
   `subprocess.STDOUT`).
5. `stdout_file` always opens text-mode and raises if `text=False`.

One lives in populate itself:

6. Idempotency checking is O(n²): the client re-fetches full live state per
   create call (34 issues = 34 ListIssues). Fetch one snapshot per run and
   pass it through — functional-core / imperative-shell, which is the
   pattern the scripts already aspire to.

## The vendored-utils decision (present options; William chooses)

The template's scripts must be self-contained for consumers. Two honest
options:

- **(A) Vendor a minimal `_utils` subset** (pipeline_types + file_ops +
  command_runner, with the #293 fixes applied) inside the template's
  scripts directory. The template then becomes the UPSTREAM of the shared
  functional library, and downstream projects re-vendor from it (the
  adoption stage below closes #293's utils half). Keeps the Result idioms
  the newest scripts use.
- **(B) Rewrite the template's scripts dependency-free** (air's standalone
  populate shows the shape). Simpler template, no library to maintain, but
  loses the house Result style and forks the code away from the three
  projects' current implementations.

Recommend one with tradeoffs stated. The 2026-08-13 cross-project utils
sync makes (A) maximally cheap right now: all three copies are identical,
so fix-once-propagate has no merge conflicts anywhere.

## The contract (state this explicitly in the README)

- `docs/GITHUB_PROJECT.md` owns STRUCTURE: milestones, labels, issue
  bodies, hand-written prose, dependency graphs. Humans (and Claude) edit
  it.
- GitHub owns STATE: issue numbers, open/closed, assignees.
- `populate` pushes structure → GitHub (create labels/milestones/issues,
  write issue numbers back into the file).
- `update` pulls state → the file, rewriting ONLY the generated regions
  between markers; hand prose is never touched by scripts.

## Naming decision (already made — implement it)

The state-pulling operation is called **update**, not "render": the
user-facing verb is `make update`, and the script is
`gh_project_update.py`. Rationale: "update" names the user's intent (bring
GITHUB_PROJECT.md up to date); "render" named the mechanism. One ambiguity
to neutralize in the README: "update" could be misread as the push
direction — include a small two-row direction table (populate: file →
GitHub; update: GitHub → file) near the top.

## Design requirements (hard-won; treat as requirements, not suggestions)

1. **Idempotent**: re-running populate skips everything that exists (and
   does so via the snapshot pattern — see known issue 6).
2. **Crash-safe write-back**: issue numbers are written back to the file
   immediately after EACH creation, not at the end — an interrupted run
   must never cause duplicates on rerun.
3. **Dry-run-first** (`--dry-run` prints every mutation), **staged**
   (`--labels-only`, `--milestones-only`, `--issues-only`,
   `--start-from`), **rate-limit-aware** (`--delay`, default ~1s).
4. **Label reconciliation, not label imposition**: before creating labels,
   read the repo's existing labels; detect near-collisions (case, spacing:
   `era: conway` vs `era:conway` is a real incident from William's
   history) and report/skip rather than silently creating a parallel
   scheme. Never force-overwrite an existing label's color/description
   silently.
5. **Freshness story**: local `update` needs `gh` auth, but a workflow
   running ON GitHub has `GITHUB_TOKEN` with issues:read. Include an
   optional scheduled Actions workflow that runs the update and commits
   (or opens a PR) when the generated regions drift. Make it opt-in — a
   template consumer may not want bot commits.
6. **Upgrade path**: template consumers fork at creation time and never
   see improvements. Ship a VERSION marker in the scripts directory plus a
   documented one-liner to re-vendor the scripts from the latest tagged
   release. Keep the scripts a self-contained directory to make that safe.
   (This same mechanism is how William's three existing projects will
   adopt the template's scripts — design it for them, not just for
   template-forkers.)
7. **Generalize fully**: no hardcoded repo names, label sets, milestone
   counts, or Agda-isms. The shipped `docs/GITHUB_PROJECT.md` is a small
   worked example (2 milestones, ~4 issues) that a consumer replaces.
   `--repo` comes from the CLI or a config header in the file itself.
8. **Makefile** (the primary UX): at minimum
   - `make populate-dry` / `make populate`
   - `make update`
   - `make lint` — no-network structural validation of GITHUB_PROJECT.md
     (markers balanced and uniquely named, `## Labels` section parses,
     milestone references consistent, issue headings well-formed). Cheap,
     CI-able on every PR — the closest thing to a drift gate this design
     admits without network.
   - `make test` — the fixture suite (requirement 12).
   - `make help` as the default target.
9. **Nix, strictly optional**: a `flake.nix` exposing a devShell (python3,
   gh, gnumake) so a user without Python can `nix develop` and go. The
   README documents BOTH paths. CI for this repo itself must NOT require
   Nix (use setup-python), so consumers aren't Nix-bound.
10. **In-repo Claude config as product**: commit `.claude/skills/` with (at
    least) one skill for "set up a new project from GITHUB_PROJECT.md" and
    one for "keep the roadmap current" (populate/update workflow), plus a
    repo-root `CLAUDE.md` explaining the contract. This is deliberate:
    committed Claude config is for a repo's CONSUMERS (template users get
    the workflow knowledge automatically); personal-workflow config lives
    in William's separate claude-tooling repo, whose manifest already
    lists this repo as `mode = "committed"` — the installer never touches
    it.
11. **Python follows the `functional-python` skill**: typed throughout,
    Result-style error handling (per the vendoring decision), pure
    parsing/diffing core with `gh` calls at the edges, `File:` docstring
    headers, tests for the pure logic. Directory layout: decide fresh
    (plain `scripts/` is fine; do not inherit `scripts/python/` by
    reflex). Python 3.11+; `gh` CLI is the auth mechanism for local runs.
12. **Repo CI**: `make lint` against the example file + script self-tests
    on fixtures (a fake GITHUB_PROJECT.md; a recorded fake `gh` transcript
    for the client; no network) + shellcheck/basic Python lint. The
    end-to-end test below stays manual.

## Quality gates (do not declare done without these)

- All six #293 items demonstrably fixed in this repo's copies, each with a
  regression test.
- End-to-end test against a THROWAWAY GitHub repo created under William's
  account (ask first): populate --dry-run → populate → update → close one
  issue on GitHub → update again (see the state flip) → re-run populate
  (verify zero duplicates). Delete the throwaway afterward.
- Every command in the README actually executed as written, from a fresh
  clone, via BOTH the plain path and the Nix path.
- The scheduled-update workflow tested at least once via workflow_dispatch.

## Follow-up stage (plan for it; do NOT do it in this session)

After the template is solid: adoption PRs to agda-algebras, the website,
and air that re-vendor the template's scripts (replacing their divergent
copies), migrate any local deltas the union missed, and close
ualib/agda-algebras#293 from the aa PR. Each adoption PR is William-gated.
End state: the template is the single place these scripts improve.

## Working style

Small commits with clear messages. For big design forks (markdown parsing
strategy, Actions-update design, the vendored-utils decision), present
options with a recommendation and let William choose. A likely first
consumer of this template is a planned "skill extractor" project (mining
Claude Code session transcripts for candidate skills) — no need to design
for it, but it will be the template's maiden voyage, so keep the
quickstart genuinely follow-able.
