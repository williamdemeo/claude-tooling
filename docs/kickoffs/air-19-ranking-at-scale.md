<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-13-air-19-ranking-at-scale.md
     (authored 2026-09-10 for agda-native-air issue #19, first rung). Launch a
     fresh session from the issue's worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-13-air-19-ranking-at-scale.md` -->

# Kick-off: ranking at scale, the measured instrument and a stronger scorer (air #19)

You are starting fresh, with no memory of the sessions that shaped this.
Everything you need is in this prompt, the referenced paths, and the issues.
Push back where a plan detail seems wrong once you have read the sources;
William wants that.

You are working in the formalverification/agda-native-air repository on the
first rung of issue #19, "[M2-5] Train or integrate premise selection model",
which also absorbed proof-search P3.  This session trains nothing.  It builds
the instrument a learned ranker will be measured with, runs the two cheap
experiments the last measurement recorded as options, and replaces the
placeholder scorer with the strongest deterministic one the instrument
justifies.  The result is the demand curve for #19 and the evaluation protocol
#21 needs.  Read #19 (with its comments), #21, and the stage-two comment on
#123 first (`gh issue view N --json title,body,comments`; plain `gh issue view`
trips this repository's classic-Projects GraphQL bug).

## Why this exists

Stage two of P2 (2026-09-08, runs `p2s2-{a,b,c}`) measured retrieval over the
agda-algebras corpus on the 43-obligation suite and located the binding
constraint precisely: not the move vocabulary (the tier's golds are all single
terms) and not the machinery (the exclusion-off control committed a wholesale
needle end to end), but RANKING AT SCALE.  Wholesale imports flood the legal
pool with up to 3,025 in-scope rows, the token-overlap scorer ranks the
library's generic projections (`Overture.ℓ₁`, `∣_∣`, `∥_∥`, `𝑖𝑑`) above the
needles, and eight fixtures burn the full probe budget on ranked-but-wrong
candidates.  The scorer is a seam (`CandidateScorer` in `Retrieve.scala`)
built for exactly this moment.  Before any model, two things are owed: a cheap
way to measure ranking without a loop-hour per sweep, and the best
non-learned scorer, so a learned one has an honest bar to clear.

## Where you are

William has created the branch and a worktree tracking it, and you are
launched from that worktree's root inside `nix develop .#backend`.  Confirm
with `git status -sb`; do not create another worktree and do not switch
branches.  Local `nix` commands outside the shell need the
`env -u LD_LIBRARY_PATH` prefix on this machine.  What you need on disk, all
gitignored, is as follows.

+  The agda-algebras v0.1 corpus (224,646,301 bytes, sha256 `af864432…` per
   `docs/corpora/agda-algebras-v0.1.md`) at
   `~/git/formalverification/agda-native-air/worktrees/p2s2-sweeps/data/corpora/agda-algebras/v0.1/corpus.jsonl`;
   copy or symlink it to this worktree's `data/corpora/agda-algebras/v0.1/`.
+  The standard-library v0 corpus at
   `~/git/formalverification/agda-native-air/worktrees/123-proof-search-p2/data/corpora/agda-stdlib/v0/corpus.jsonl`.
+  The stage-two run artifacts, the baseline ledgers this session is measured
   against, under
   `~/git/formalverification/agda-native-air/worktrees/p2s2-sweeps/data/benchmarks/reports/proof-search/p2s2-{a-retrieval-peek,b-fixed-peek,c-control-noexclude}/`
   (`report.json` carries each fixture's goal display, `proposedLemmas`, hits,
   in-scope counts, and named exclusions).
+  `AGDA_MCP_BIN` may name a prebuilt server binary and skips the cabal build.

## Orientation (read before writing anything)

1.  #19 and the P3 scope absorbed into it; #21's evaluation protocol wish
    list; #123's stage-two comment and runbook; the #113 comments of
    2026-09-07 and 2026-09-08 (the suite baseline and the re-measured stage
    one).
2.  `docs/proof-search/overview.md` §§ 2, 6.2, 8 (vocabulary, the retrieval
    pipeline step by step, how to read a run), then ADR 0001 §§ 7, 9, 10.
3.  `strux-driver/src/main/scala/struxdriver/search/Retrieve.scala` in full:
    `Queries.goalTokens`, `TokenOverlapScorer`, `rankKey`, `resolveTopK`, the
    stats ledger; `RetrieveSpec` for what is pinned.  `LoopHarness.scala` for
    the `--proposer` / `--retrieve-k` / `--exclude-target` knobs and the
    report fields.
4.  `data/benchmarks/README.md`: the agda-algebras tier, its `stratum:using`
    and `stratum:wholesale` tags (11 and 10 rows), and the provenance of each
    row.  `docs/representation.md` § 3 for what a corpus row carries
    (`type`, `typeAst`, `dependencies`, `defKind`).

## The work, in order

1.  **Name the targets.**  Each agda-algebras fixture restates a library
    lemma; record, per row, the qualified name of the library lemma or lemmas
    a retrieval-found proof would apply (the wholesale rows' originals are
    reachable by construction; the `using` rows' targets are in their import
    lists).  Put it in the index as a `target:<prettyQname>` tag, one commit,
    benchmark content only; it is the ground truth every recall number below
    is computed against.
2.  **Build the offline rank-only instrument.**  A `struxdriver.search` entry
    point (a Make target with a help line) that, for each fixture, takes the
    goal display recorded in a run's `report.json` (no server needed), builds
    the legal pool from the fixture's imports and the corpus exactly as
    `RetrievalProposer` does (scope, exclusion, `defKind` filter), ranks it
    with a named scorer, and reports the rank of each target lemma, the pool
    size, and recall@8 / @32 per fixture, per stratum, and overall.  Seconds
    per sweep instead of a loop-hour; this is #21's "retrieval recall@k"
    column, decoupled from the loop.  Pin it with a canned-corpus test.
3.  **Run the two recorded knob experiments** with the loop, wholesale stratum
    only (`PROOF_SEARCH_LOOP_IDS="--ids …"` over the ten wholesale ids):
    `PROOF_SEARCH_RETRIEVE_K` at 16 and 32 against 8, and `PROOF_SEARCH_BUDGET`
    at 120 against 60, exclusion on.  Report solves, probes, and wall per
    sweep beside `p2s2-a`; these say how far ranking alone is from enough.
4.  **A stronger deterministic scorer** behind `CandidateScorer`, selectable
    by name (`PROOF_SEARCH_SCORER`, default unchanged so every published number
    reproduces).  Hypotheses to test on the instrument, in this order:
    inverse-document-frequency weighting of token overlap computed over the
    in-scope pool, which is what demotes `∣_∣` and `𝑖𝑑` without a hand list;
    a match on the conclusion's head relation and its arguments' heads, read
    from `typeAst` if the corpus carries enough structure and from the printed
    type otherwise; and a name-fragment weight under the same IDF.  Keep each
    rule only if recall@k moves; pin every rule with the fixture that
    motivated it, as the existing scorer does.
5.  **One loop sweep with the best scorer**, all 43 obligations, exclusion on
    and then off (the control), same knobs as every published sweep (beam 4,
    depth 6, budget 60, retrieve-k 8, peek on), quiet machine, zero anomalies
    required.  The stdlib rows must reproduce 6/22 byte-for-byte (their
    corpus is absent, so retrieval is inert there) and the fixed-space
    baseline must stay 8/43.
6.  **Post the demand curve** on #19 (recall@k per scorer, per stratum; what a
    learned model has to beat; which fixtures no deterministic rule reaches
    and why), the protocol as a draft on #21, and the loop numbers on #113.
    Open the PR.

## Constraints and gotchas

+  Benchmark content (the `target:` tags) and search tooling stay on separate
   commits, and the frozen stdlib tier stays byte-frozen.
+  The scorer ranks and never counts: binder counts still come from lane
   `type_of` on the accepted rendering.  Nothing in this session touches the
   loop's judging, the exclusion policy, or the candidate shapes.
+  A run whose ledger shows the exclusion firing on a target is gamed, not
   ranked; read the ledger before quoting a number.
+  Anomalies redden a run and are reported, never hidden; `make test` runs the
   pure suites without a server.
+  Corpus queries ask wide (limit 5000) because the server truncates at 20 by
   default; a query returning exactly the limit is counted as truncated.
+  House style is in the repository CLAUDE.md.  GitHub bodies: no hard wraps,
   and every issue or PR number bracketed with a definition at the bottom.
+  Never merge the PR and never request a review; triage every Copilot
   finding on evidence and reply to each, suppressed findings included.

## Done looks like

Target lemmas recorded per row; the rank-only instrument with a Make target,
a test, and a recall@k table for the current scorer; the two knob experiments
measured; a named scorer that beats token overlap on the instrument, pinned
rule by rule, with one full loop sweep confirming the published baselines and
reporting its solves; the demand curve on #19, the protocol on #21, the sweep
on #113; the PR open.  End by saying the PR is ready for review, and stop
there.
