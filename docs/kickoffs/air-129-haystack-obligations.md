<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-12-air-129-haystack-obligations.md
     (authored 2026-09-10 for agda-native-air issue #129). Launch a fresh
     session from the issue's worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-12-air-129-haystack-obligations.md` -->

# Kick-off: benchmark obligations that need a lemma from a haystack (air #129)

You are starting fresh, with no memory of the sessions that shaped this.
Everything you need is in this prompt, the referenced paths, and the issue.
Push back where a plan detail seems wrong once you have read the sources;
William wants that.

You are working in the formalverification/agda-native-air repository on issue
#129, "[M2-11] benchmarks: obligations whose single-term golds require
retrieval from imported haystacks".  Read it first (`gh issue view 129 --json
title,body,comments`; plain `gh issue view` trips this repository's
classic-Projects GraphQL bug).  It is the specification; this prompt is the
operating manual.

## Why this exists

Proof search P2 measured retrieval twice and found the same thing both times:
retrieval adds zero solves under target exclusion, and a labeled control with
exclusion off proves the machinery (it retrieves, ranks, renders, saturates,
and commits every stdlib target the exclusion had removed, and one wholesale
needle on agda-algebras).  The reason is the suite, not the retriever: every
standard-library obligation IS a standard-library lemma, so with the answer
key excluded there is no needle left that is not the answer key, and the
term-mode ceiling binds the rest.  This issue builds the instrument that is
missing: obligations whose single-term golds require a lemma that is
import-reachable but not `using`-listed and not the obligation's own
statement.  Every later ranking result (issue #19, #21) will be quoted on
these rows, so they must be built to the letter of the design constraints.

## Where you are

William has created the issue branch and a worktree tracking it, and you are
launched from that worktree's root inside `nix develop .#backend` (Agda 2.8.0,
standard-library 2.3, GHC, sbt).  Confirm with `git status -sb` (a branch named
for issue 129, clean, tracking origin); do not create another worktree and do
not switch branches.  Local `nix` commands outside the shell need the
`env -u LD_LIBRARY_PATH` prefix on this machine.

## Orientation (read before writing anything)

1.  Issue #129 (the specification) and the design comment on #123 (the scope
    rule, the exclusion rules, the candidate shapes, and the wire fact that
    `fill_hole` refuses blocked-constraint sub-holes).
2.  `docs/proof-search/overview.md`, §§ 2 and 6.2: the vocabulary and the
    retrieval pipeline; then ADR 0001 (`docs/adr/0001-proof-search-on-agda-mcp.md`)
    § 7 and § 9 for the decisions and the numbers the new rows must be
    interpretable against.
3.  `data/benchmarks/README.md` (the index schema, the fixture convention, the
    frozen stdlib tier) and `docs/benchmarks/taxonomy.md` (the tiers).
4.  The project skill `authoring-a-benchmark-obligation`: project skills are
    invisible from a worktree, so read it at
    `~/git/williamdemeo/claude-tooling/main/projects/agda-native-air/claude/skills/authoring-a-benchmark-obligation/SKILL.md`,
    and `typechecking-agda` beside it.
5.  The five frozen fixtures that import a `Properties` module, as models of
    the import shape: `stdlib-nat-plus-comm`, `stdlib-nat-mul-comm`,
    `stdlib-nat-mul-assoc`, `stdlib-nat-mul-distrib-l`,
    `stdlib-nat-mul-distrib-r` (paths in `data/benchmarks/benchmark-index.jsonl`).
6.  `strux-driver/src/main/scala/struxdriver/search/Retrieve.scala`, header
    and `TargetExclusion`, `Statements.normalize`, `shapes`: what the exclusion
    fires on and which candidate shapes the proposer can emit.
7.  PR #143 (per-directory fixture `.agda-lib` files, stacked on #132): if it
    has merged, a new fixture directory needs the same pair (two files, never
    one shared, or twin module names go ambiguous).

## The work, in order

1.  **Design the slice on the issue before writing Agda.**  Post a comment on
    #129 listing the obligations you intend to write (target eight to twelve):
    for each, the imported `Properties`-family module and its narrow `using`
    list, the novel composite statement, the haystack lemma or lemmas the gold
    applies, the candidate shape the gold takes (saturated application over
    the context, the `_`-form, or a `{!!}`-refinement through a
    top-level-meta conclusion), and the difficulty tier.  Vary the haystack:
    `Data.Nat.Properties` for most, but at least two other modules (list,
    order, or algebra properties), so the measurement is not one module's.
2.  **Write them under a new tier directory**, not into the frozen
    `agda-stdlib-v0` (that tier only ever grows by whole new tiers).  Suggested
    name: `data/benchmarks/agda-stdlib-haystack-v0/{obligations,gold}/`.  Each
    obligation: one module, one `{!!}` hole, `AgdaDojang.Debug` plus the
    minimal imports, the module name equal to the file stem.  Each gold: the
    same module with the hole filled by a single term.
3.  **Enforce the three design constraints mechanically.**  (a) The gold
    lemma's bare name must differ from the hole's name.  (b) The obligation's
    stated type must not normalize to any corpus row's type: check it against
    the stdlib corpus with the same normalization the proposer uses
    (`Statements.normalize`); a one-off script in `scripts/python/` under the
    house Python style is fine.  (c) The fixed space must fail every row:
    run `make proof-search-loop PROOF_SEARCH_PROPOSER=fixed
    PROOF_SEARCH_LOOP_IDS="--ids <the new ids>"` and confirm every status is
    `exhausted` or `budget_exceeded`.
4.  **Measure the rows with retrieval, exclusion on.**  The corpus is
    gitignored; take the standard-library v0 corpus from
    `~/git/formalverification/agda-native-air/worktrees/123-proof-search-p2/data/corpora/agda-stdlib/v0/corpus.jsonl`
    (462 MB; digest in `docs/corpora/agda-stdlib-v0.md`) into this worktree's
    `data/corpora/agda-stdlib/v0/`, or rebuild it with `make corpus-stdlib-nix`
    (about five minutes).  Run the loop with `PROOF_SEARCH_PROPOSER=retrieval`
    on the new ids and read `report.json`: the exclusion ledger must show zero
    firings on these rows (constraint from the issue), and the per-fixture
    `proposedLemmas` tells you whether the current token-overlap ranker even
    surfaces the needle.  A row the ranker cannot find is a valid instrument,
    not a defective fixture; record the outcome per row.
5.  **Index, docs, and gates.**  One `benchmark-index.jsonl` row per
    obligation with a tag that identifies the tier (check how `EvalBenchmark`,
    `Scaffold.readIndex`, and `LoopHarness` group rows, by `source`,
    `difficulty`, and `tags`, and choose the discriminator that keeps the
    frozen 22 reportable on their own; if that needs a small harness change,
    make it its own commit, since benchmark content and tooling are separate
    concerns).  Add a tier section to `data/benchmarks/README.md` in the shape
    of the agda-algebras one.  `make eval-benchmark` must verify every gold
    under the pinned toolchain; `make eval-benchmark-smoke` and `make test`
    stay green.
6.  **Post the per-row table** (id, haystack module, target lemma, shape,
    tier, fixed-space status, retrieval status, exclusion firings) on #129 and
    as a comment on #113 ([M2-9]), and open the PR.

## Constraints and gotchas

+  The frozen stdlib tier is untouched, byte for byte: the P1 and P2 baselines
   are quoted against it.
+  A gold that needs a shape the proposer cannot emit measures the shape
   vocabulary, not retrieval; keep golds within the three committed shapes.
+  `open import M using (xs)` grants qualified access to all of `M`; that is
   the fact the whole instrument rests on, and it is why the `using` list must
   stay narrow.
+  Loop timings are comparable only on a quiet machine; the solve set,
   scripts, and probe counts are the columns to compare.
+  `AGDA_MCP_BIN` may name a prebuilt server binary and skips the cabal build.
+  House style is in the repository CLAUDE.md.  GitHub bodies: no hard wraps,
   and every issue or PR number bracketed with a definition at the bottom.
+  Never merge the PR and never request a review.  If a Copilot review lands,
   triage every finding on evidence and reply to each, suppressed findings
   included (the `handling-copilot-pr-reviews` skill).

## Done looks like

Eight to twelve obligations with typechecking golds under a new tier
directory; every row failing the fixed space and firing zero exclusions;
retrieval measured per row with the honesty ledger quoted; index rows and the
README tier section in place; `make eval-benchmark` green over the whole
suite; the table posted on #129 and #113; the PR open.  End by saying the PR
is ready for review, and stop there.
