<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-11-fls-1274-batch-threading-invariants.md
     (authored 2026-09-08 for formal-ledger-specifications issue #1274). Launch
     a fresh session from the new worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-11-fls-1274-batch-threading-invariants.md` -->

# Kick-off: batch-threading UTxO invariants for LEDGER-pov (fls #1274)

## Setting

Work happens in a NEW worktree of IntersectMBO/formal-ledger-specifications.
Create it from the master checkout, cutting the branch from the TOP of the
Dijkstra PoV stack:

    cd ~/git/IO/fls/master
    git fetch origin
    git worktree add -b 1274-dijkstra-batch-threading-utxo-invariants \
        ../worktrees/william/1274-dijkstra-batch-threading-utxo-invariants \
        origin/1276-dijkstra-gov-pov
    ln -s ~/git/IO/fls/.claude \
        ../worktrees/william/1274-dijkstra-batch-threading-utxo-invariants/.claude

Work inside `nix develop` there (or prefix agda commands with
`nix develop --command`).  Verify before starting: `git rev-parse --abbrev-ref
HEAD`, `git fetch origin`, `agda --version` (2.8.0).  The eventual PR is a
draft targeting `1276-dijkstra-gov-pov`; GitHub retargets it down the stack as
the PRs below merge.

## Stack context (as of 2026-09-08)

The Dijkstra PoV stack is #1189 (`1186-dijkstra-utxo-and-utxow-pov`, based on
master) → #1210 (`1185-dijkstra-NEW-ENTITIES-certs-pov`) → #1278
(`1276-dijkstra-gov-pov`).  All three are MERGEABLE with green CI, and each
already REWIRES `Ledger.Properties.PoV`: the UTxO, Certs, and gov facts are
imported from the property modules that prove them, not assumed.  At the top
of the stack, `module LEDGER-PoV` has exactly TEN parameters left: the three
`ApplyToRewards` set/map identities, `noMintSubTx`, the four batch-threading
invariants (`utxo₁-tx-spend-eq`, `fresh-top-tx-id`, `subtx-fresh-txid`,
`subtx-spend-agree`), and the two withdrawal bounds (owned by #1275).

## Mission

Issue #1274: eliminate the UTxO-side residue.  In order:

1. RESTATE the four batch-threading invariants so they are provable (see the
   critical warning below), prove them, and rewire `LEDGER-PoV` and
   `SUBUTXOW-PoV` (in `Utxow.Properties.PoV`) to consume the proofs.
2. Collect `noMintSubTx` from the `SUBLEDGERS` derivation (fact 3 of the
   issue) so it also stops being a parameter.  Structural wrinkle: `open
   UTXOW-PoV tx noMintSubTx` currently happens at module level inside
   `LEDGER-PoV`, but the collected fact is only available per LEDGER step
   (from `subStep` inside the `LEDGER-V` case), so the opens or the lemma
   applications must move accordingly.
3. End state: `LEDGER-PoV` keeps only the three `ApplyToRewards` identities
   and the two withdrawal bounds (ten parameters down to five).

Read issue #1274's body first; its Notes section sketches the intended
running-UTxO invariant and is accurate.

## CRITICAL: the four statements are FALSE as stated

Do not attempt to discharge the parameters verbatim (memory
`fls-batch-threading-hypotheses-false`, finding of 2026-08-06):

- `subtx-fresh-txid` / `fresh-top-tx-id`: nothing stops the arbitrary running
  state `s₀` from already containing a key whose first component is the
  transaction's own TxId, and `fresh-top-tx-id` is additionally falsified by
  the reflexive `SUBLEDGERS` case.
- `subtx-spend-agree` / `utxo₁-tx-spend-eq`: the premises put the spend
  inputs in both domains (snapshot and running) but say nothing about the
  VALUES stored there.

What makes them true is the batch history: the running UTxO is built from the
pre-batch snapshot by removing spent inputs and adding outputs keyed by fresh
TxIds.  Restate the whole family together: either quantify `s₀` over states
reachable from `UTxOOf Γ` by the preceding sub-steps, or thread a
`SUBLEDGERS`-level running-UTxO invariant, then derive all four.  The
consumers (`subutxow-step-coin`'s proof in `SUBUTXOW-PoV`, and `LEDGER-pov`'s
own body at its `mech` and `bat'` steps) must be adapted to the restated
forms coherently.

## Read before writing

- Issue #1274 (body and Notes).
- The `UTXO` rule in `src/Ledger/Dijkstra/Specification/Utxo.lagda.md`.
  Answer the issue's open question: do the rule's batch premises actually
  provide distinctness of the batch's TxIds and their absence from the
  pre-batch UTxO, or is a new spec premise required?  A spec-side premise is a
  SEMANTIC change (CHANGELOG entry, Carlos sign-off): if one is needed, STOP
  and present the options before editing the spec.
- `module LEDGER-PoV` (parameter block and body) in
  `src/Ledger/Dijkstra/Specification/Ledger/Properties/PoV.lagda.md`; the use
  sites are `SUBLEDGERS-utxo-coin`, `mech`, and `bat'`.
- `module SUBUTXOW-PoV` in `…/Utxow/Properties/PoV.lagda.md` and
  `subutxo-step-coin` in `…/Utxo/Properties/PoV.lagda.md`.
- Skills: `fls-pov-dropin-check` (re-run whenever statements or branches
  move), `fls-github-pr-ops`, `agda-typecheck`, `agda-ring-solver`.

## Ground rules

- `--safe` throughout; no postulates, no termination pragmas.
- Never push to `1276-dijkstra-gov-pov`, `1185-…`, `1186-…`, or `master`;
  push only `1274-dijkstra-batch-threading-utxo-invariants`, with
  `--force-with-lease`.
- Small clear commits authored by William; nontrivial AI commits end the body
  with `AI-assisted development: <model> (Anthropic)`; never a Co-Authored-By
  trailer.
- Module prose: iterative-deepening style, concise; no status, roadmap, or
  issue-number talk in module documentation.
- Gates before every push: per-file agda on touched modules, full
  `agda src/Ledger.lagda.md`, and
  `python3 build-tools/scripts/property-tracking/scan_properties.py --check`
  whenever the catalog or a property module changed.
- PR: draft, VERY concise bullet-point body (no em-dashes), with the headline
  bolded (which parameters die and what the contract shrinks to).  `gh pr
  edit` is broken on this repo; use `gh api repos/…/pulls/N -X PATCH` per the
  fls-github-pr-ops skill.
- End with a report: the restated statements (before and after), what is
  proved versus still assumed, the spec-premise decision if one arose,
  verification status, and anything Carlos must decide.
