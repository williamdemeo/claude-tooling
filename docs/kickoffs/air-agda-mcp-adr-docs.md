<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-10-air-agda-mcp-adr-docs.md
     (authored 2026-09-07 for agda-native-air issue #148). William will have
     created the issue branch and a worktree tracking it under
     ~/git/formalverification/agda-native-air/worktrees/, and `claude` is
     launched from that worktree root. Then:
     Read and execute `~/claude-kickoff-prompts/kickoff-10-air-agda-mcp-adr-docs.md` -->

# Kick-off: ADR 0002 (agda-mcp) and the docs/ reorganization (issue #148)

You are starting fresh, with no memory of the sessions that shaped this.  Everything you need is in this prompt, the referenced paths, and the issue.  Push back where a plan detail seems wrong once you have read the sources; William wants that.

You are working in the formalverification/agda-native-air repository on GitHub issue #148, "[M1-9] docs: ADR 0002 — the agda-mcp design record, plus a docs/ reorganization".  Read the issue first (`gh issue view 148 --json title,body` — plain `gh issue view` trips this repository's classic-Projects GraphQL bug); it carries the full plan: the decision list for the ADR with each decision's primary sources, the `docs/` reorganization steps, the boundaries, and the acceptance criteria.  Treat the issue as the specification and this prompt as the operating manual.

## Where you are

William has already created the issue branch and a worktree tracking it, and you are launched from that worktree's root.  Confirm with `git status -sb` (a branch named for issue 148, clean, tracking origin); do not create another worktree and do not switch branches.  The work is documentation-only: no Agda needs to be written, and the toolchain matters only for the final sanity run.

## Orientation (read before writing anything)

1.  Issue #148 — the specification.
2.  `docs/adr/0001-proof-search-on-agda-mcp.md` — the house ADR format you are matching: context, decisions each with status and evidence, a decision-log table, references.  Note its density: decisions and the measurements that earned them, no restated tutorials.
3.  The four source notes the ADR distills: `docs/agda-mcp-interaction-lane.md`, `docs/agda-mcp-ask-agda-audit.md`, `docs/agda-mcp-environment.md`, `docs/agda-mcp-improvements-summary.md`.
4.  The evidence record: `docs/mcp-field-reports.md` (nine field sessions), `docs/feedback/flrp-agda-mcp-improvements.md` and `docs/feedback/agent-case-for-corpus-proof-search.md` (the consumer-side documents), and `agda-mcp/README.md` (the shipped tool contracts).
5.  The issue tree for provenance links: the closed #68 wave (#69–#79), #101/#106/#108/#114/#115, and Milestone 5 (#134–#139, #145–#147) for the open follow-ups an honest ADR names.

## The work, in order

1.  **Write `docs/adr/0002-agda-mcp.md`** per the issue's decision list.  Every decision cites its source document and issue numbers; open follow-ups are named (the Milestone 5 issues), not hidden.  Concise beats complete: the deep notes remain the record, the ADR states what was decided and why it stands.
2.  **Reorganize `docs/`** per the issue: create `docs/agda-mcp/`, `git mv` the four server notes into it, and add the short `docs/README.md` index.  Keep the move commit free of content edits (renames must review as renames); fix references in a separate commit if any file needs edits beyond its path.
3.  **Update every reference to moved files.**  Grep the entire repository (`docs/`, `README.md`, `Makefile`, `.github/`, `agda-mcp/`, `strux-driver/`, `scripts/`), then grep the claude-tooling repository (`~/git/williamdemeo/claude-tooling/main`, both `global/` and `projects/`) for the old paths — the agda-algebras `CLAUDE.md` standing instruction references `docs/mcp-field-reports.md` by path, which is exactly why the issue makes that file a special case: leave it in place, or move it and update the claude-tooling instruction in the same change (then run `make install PROJECT=agda-algebras` there).  State which option you took in the PR.
4.  **Link-check** `docs/` (a scripted pass over relative links is fine) and run `env -u LD_LIBRARY_PATH make test` as the cheap repo sanity; CI runs the full pipeline on the PR.
5.  **Open the PR** (standing authorization in CLAUDE.md; no need to ask).  The description lists: the ADR's decision inventory, the move map, the field-reports choice, and the overlaps the issue says to flag for William rather than resolve (`roadmap.md` vs `PLAN.md` vs `GITHUB_PROJECT.md`; `WORKFLOW.md` vs its cheatsheet).

## Constraints and gotchas

+  `docs/GITHUB_PROJECT.md` is engine-generated in its marked regions: do not touch it.  ADR 0001 has pending edits on open PRs (#130, #132): 0002 must not modify 0001, and nothing in this task should touch files those PRs edit.
+  Local `nix` commands need the `env -u LD_LIBRARY_PATH` prefix on this machine.
+  House style is in the repository CLAUDE.md (bullets with `+`, two spaces after sentence-ending periods, semicolons append sentences and em-dashes only phrases); GitHub-bound bodies (PR description, comments) are never hard-wrapped — one source line per paragraph or bullet.
+  Never merge the PR and never request a review — both are William's actions alone.  If a Copilot review lands, triage every finding on evidence and reply to each comment, suppressed findings included (the `handling-copilot-pr-reviews` skill covers the mechanics, including the suppressed-comments trap and the classic-Projects `gh` workarounds).
+  Deliver commit messages in the repository's voice (see `git log`); keep the move commit and the content commits separate.

## Done looks like

Issue #148's acceptance criteria, verbatim: the ADR exists in 0001's format with every decision sourced; moved references all resolve; `docs/README.md` indexes the directory; CI is green; the PR flags rather than resolves the judgment calls.  End by saying the PR is ready for review — and stop there.
