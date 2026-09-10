<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-14-air-17-search-in-scope.md
     (authored 2026-09-10 for agda-native-air issue #17, phase 1). Launch a
     fresh session from the issue's worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-14-air-17-search-in-scope.md` -->

# Kick-off: `search_in_scope`, retrieval as an agda-mcp tool (air #17, phase 1)

You are starting fresh, with no memory of the sessions that shaped this.
Everything you need is in this prompt, the referenced paths, and the issue.
Push back where a plan detail seems wrong once you have read the sources;
William wants that.

You are working in the formalverification/agda-native-air repository on phase
1 of issue #17, "[M2-3] Add retrieval tools to agda-mcp: corpus-backed
search".  Read the issue and its design comment of 2026-09-08 first
(`gh issue view 17 --json title,body,comments`; plain `gh issue view` trips
this repository's classic-Projects GraphQL bug).  The comment is the design;
this prompt is the operating manual.  Phase 2 (`search_term`, bounded
synthesis at a hole) is a later session.

## Why this exists

Proof search P2 built scope-aware retrieval inside the Scala search driver,
and the consumer-side brief written from real agda-algebras sessions
(`docs/feedback/agent-case-for-corpus-proof-search.md`) found that the
dominant cost of a session is discovering what exists in the library and what
it is called, by grep and reading, at tens of seconds per question.  The
brief's own sequencing puts a scope-aware retrieval tool first, ahead of
synthesis and ahead of learned ranking, because soundness and latency matter
more than ranking quality when the agent can triage a handful of candidates
itself.  Everything the tool needs exists in the driver today; the work is a
server-side contract, the scope computation from the loaded file, and the
transport.

## Where you are

William has created the issue branch and a worktree tracking it, and you are
launched from that worktree's root inside `nix develop .#backend` (GHC, Cabal,
Agda 2.8.0, sbt).  Confirm with `git status -sb`; do not create another
worktree and do not switch branches.  Local `nix` commands outside the shell
need the `env -u LD_LIBRARY_PATH` prefix on this machine.  Build the server
with `cabal build exe:agda-mcp` (the `lib:` target trips a Cabal defect);
`make agda-mcp-test` runs the suite and is NOT concurrent-safe (it patches
in-repo fixtures in place), so never run two at once.

## Orientation (read before writing anything)

1.  #17 with its design comment: the four requirements (checked terms only;
    scope-awareness through the checker; honest negatives with stated bounds;
    latency that beats grep-plus-read), what transfers from the driver, and
    the proposed `search_in_scope` shape.
2.  ADR 0002 (`docs/adr/0002-agda-mcp.md`), §§ 2, 3, 4, 10: the two-lane
    policy (a tool informs, never decides), the response echo, the ask-Agda
    rule, and the corpus tools as they stand.  `docs/agda-mcp/agda-mcp-interaction-lane.md`
    §§ 3 and 5 for the lane's lifecycle and the live-query tools' shape.
3.  `agda-mcp/README.md`: the tool surface, the echo tables, the corpus-tools
    section, and the rule that a tool description carries the client-visible
    contract.
4.  The Haskell: `AgdaMCP/Tools/Search.hs` (the three lookups), `Corpus.hs`
    (the index), `Tools/LiveQueries.hs` and `Interaction.hs` (the lane),
    `Holes.hs` (the code-only view, where imports are read), `Types.hs`
    (response types and their JSON), `Server.hs` (registration and schemas).
5.  The driver's implementation to port from, not to call:
    `strux-driver/src/main/scala/struxdriver/search/Retrieve.scala`
    (`ImportScope`, the rendering ladder in `resolve`, `TargetExclusion`,
    `RetrievalStats`) and `Imports` in `Propose.scala`.
6.  The project skill `driving-agda-mcp`, read at
    `~/git/williamdemeo/claude-tooling/main/projects/agda-native-air/claude/skills/driving-agda-mcp/SKILL.md`
    (project skills are invisible from a worktree): how to verify a tool's
    description and response body on the real stdio transport rather than
    infer them from the Haskell.

## The work, in order

1.  **Settle the contract on the issue first.**  Post a comment on #17 with
    the input schema (`filePath`, an optional `line`/`column` scope anchor,
    `query` as a name pattern and/or type tokens, `limit`, an optional
    `exclude` of names and/or a statement), the output rows (`prettyQname`,
    the accepted rendering, the lane-printed type, the reachability route,
    that is which import admits it, and `module`), the honesty ledger block
    (hits, in-scope, excluded by name and by statement, non-function, lane
    rejected, truncated at limit), the in-band error shape, and the lane echo.
    State in the description that the tool informs and never decides a
    verdict, and what an empty result means with its bounds.
2.  **Scope from the loaded file, server-side.**  Read the file's
    `open import M [using (…)]` lines off the code-only view (the lane has no
    command that enumerates imports, so this is a derived answer under the
    ask-Agda rule: say so in the module header, and subordinate it by
    validating every rendering through lane `type_of`).  A row is reachable
    iff its module equals an imported module or extends one at a dot boundary;
    a whole-module `open import` admits all of the module.
3.  **Rank and render.**  Port the token-overlap scorer as the phase-1
    ranking (the seam in the driver may grow a better scorer in parallel; keep
    the server's ranking behind one function so it can follow).  Render each
    of the top rows through the ladder (bare when `using`-listed, the
    qualified name, the importing module qualifying the bare name) and accept
    only a rendering the lane types; the cut to `limit` is taken after
    resolution so a rejected rendering does not consume a slot.
4.  **Register the tool** behind `--corpus` like the three lookups, with a
    declared input schema (an argument the handler accepts must be a declared
    property, not description prose) and a description that carries the
    contract.  Every place that asserts the tool count or list moves from
    thirteen to fourteen: grep for `thirteen` and `Thirteen` in
    `agda-mcp/README.md`, `docs/architecture.md`, `docs/HowToRun.md`,
    `docs/adr/0002-agda-mcp.md`, and the Makefile help.
5.  **Tests and captures.**  Pure tests for scope, the ladder order, the
    exclusion rules, and the ledger arithmetic; a tier-3 live test against the
    fixture corpus (`agda-mcp/test/resources/corpus-fixture.jsonl`) and a
    fixture file with narrow `using` imports, asserting a `using`-listed name
    renders bare, a nested row renders qualified, and an out-of-scope row is
    absent and counted; the description and a full response captured over the
    real transport per the skill.
6.  **Measure latency on a real corpus** (the agda-algebras v0.1 corpus lives
    at `~/git/formalverification/agda-native-air/worktrees/p2s2-sweeps/data/corpora/agda-algebras/v0.1/corpus.jsonl`,
    224 MB): the pool-and-rank time and the per-candidate lane time,
    separately, on a warm lane and on a cold one, and post them on #17 beside
    the issue's `< 100 ms` acceptance figure for the lookup half.
7.  **Docs**: the README's tool tables and a short section in the shape of
    the live-queries one; one line in ADR 0002's § 10 status noting phase 1
    landed; the PR.

## Constraints and gotchas

+  The two-lane policy is absolute: this tool answers from the corpus and the
   lane and never carries `success` or `verdict`.
+  A wrong tree is an error, not a wrong answer: resolve and refuse the path
   exactly as the batch tools do (issues #101 and #76), so the scope is the
   right file's.
+  Exclusion is client policy: the server excludes only what the caller
   passes, and names every exclusion in the response.
+  Strict decoders on the driver side will not see this tool yet; nothing in
   `strux-driver` changes in this session.
+  Structural `typeAst` matching for `search_by_type` is on the issue's task
   list and is out of scope here; say so in the PR.
+  House style is in the repository CLAUDE.md.  GitHub bodies: no hard wraps,
   and every issue or PR number bracketed with a definition at the bottom.
+  Never merge the PR and never request a review; if a Copilot review lands,
   triage every finding on evidence and reply to each, suppressed findings
   included (the `handling-copilot-pr-reviews` skill).

## Done looks like

The contract agreed on #17; `search_in_scope` registered with a declared
schema and a contract-carrying description; scope computed from the loaded
file and every rendering validated by the lane; the ledger in every response;
pure and live tests green with `make agda-mcp-test`; the tool count updated
everywhere it is asserted; latency numbers on #17; the PR open.  End by saying
the PR is ready for review, and stop there.
