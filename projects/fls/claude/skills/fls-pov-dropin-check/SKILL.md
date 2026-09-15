---
name: fls-pov-dropin-check
description: Mechanically verify that a Dijkstra PoV PR's lemmas discharge the LEDGER-PoV module parameters VERBATIM, by elaborating a throwaway wiring module end-to-end under --safe. Use when reviewing or finishing any PR in the stacked PoV family (UTxO/UTxOW, Certs, Gov, Entities) whose contract is "statements match the consumer's parameter block verbatim", and re-run it whenever either branch of the stack moves.
---

# Drop-in verification against the LEDGER-PoV contract

The consumer is `module LEDGER-PoV` in
`src/Ledger/Dijkstra/Specification/Ledger/Properties/PoV.lagda.md` (on the PR's
*base* branch): a positional block of module parameters, some of which the PR
under review claims to discharge.  Eyeballing "verbatim" is not enough — the
proof is a throwaway wiring module that Agda elaborates end-to-end.

## Procedure

1. Work in the PR's worktree with the stack in place (`git merge-base` of the
   PR branch and its base must equal the base's head).  Read the consumer's
   parameter block and note which parameters the PR discharges.

2. Create `src/PoVWiringCheck.agda` (`src` is on the include path via
   `formal-ledger.agda-lib`, so the top-level module name is just
   `PoVWiringCheck`).  Skeleton:

   + `{-# OPTIONS --safe #-}`, then mirror the consumer's own header: the same
     `(txs : _) (open TransactionStructure txs) (abs : AbstractFunctions txs)
     (open AbstractFunctions abs)` module telescope and the same
     `open import Ledger.Dijkstra.Specification.*` block
     (Certs/Entities/Gov/Gov.Actions/Ledger/Utxo/Utxow), plus
     `open import Interface.STS` and `open RewardAddress`.
   + Import the consumer restrictively —
     `using (module LEDGER-PoV; proposalsOf)` — because provider and consumer
     may both define helpers like `noMintingSubTxs` (duplicate definitions are
     fine at wiring time when they unfold to the same type; restricting the
     import avoids the ambiguity).
   + Import the PR's provider modules (`Utxo.Properties.Base`,
     `Utxo.Properties.PoV`, `Utxow.Properties.PoV`, …).

3. Declare an inner `module Check` taking `tx : TopLevelTx`
   `(let open Tx tx; open TxBody txBody)`, then **every parameter the PR does
   NOT discharge, copied verbatim from the consumer's block**, then any
   hypotheses the provider modules themselves take (older branches of the
   stack: `SUBUTXOW-PoV`'s two batch-threading hypotheses; once the batch
   invariant is proved the providers take none).  Extract the block
   programmatically rather than by hand, so "verbatim" is guaranteed:

   ```python
   src = open("src/Ledger/Dijkstra/Specification/Ledger/Properties/PoV.lagda.md").read()
   head = "module LEDGER-PoV\n  (tx : TopLevelTx) (let open Tx tx; open TxBody txBody)\n"
   i = src.index(head) + len(head); block = src[i:src.index("\n  where\n", i)]
   ```

4. In the body, instantiate the provider modules, then apply `LEDGER-PoV`
   positionally with the discharged slots filled by provider lemmas and the
   rest passed through.  On a branch where the consumer already imports its
   providers, the block is just the residual parameters (five, once the batch
   invariant is proved):

   ```agda
   open LEDGER-PoV tx
     ∪ˡ-lookup-preserve sum-map-proj₂≡getCoin setToList-Unique
     ENTITIES-wdrls-bounded SUBENTITIES-wdrls-bounded
   ```

   On an older branch the discharged slots are filled in place, e.g.

   ```agda
   open UTXOW-PoV tx noMintSubTx
   open SUBUTXOW-PoV subtx-fresh-txid subtx-spend-agree

   open LEDGER-PoV tx
     ∪ˡ-lookup-preserve sum-map-proj₂≡getCoin setToList-Unique
     (λ {u} {u'} → balance-∪ u u')
     split-balance  noMintTx noMintSubTx
     (λ {u} → outs-disjoint tx {u})
     subutxow-step-coin  utxo₁-tx-spend-eq fresh-top-tx-id
     ...
     utxow-pov-invalid UTXOW-V-mechanical UTXOW-batch-balance-coin
   ```

   η-expansion gotcha: lemmas exported from *anonymous* modules with implicit
   parameters (`module _ {utxo utxo' : UTxO}`) will not unify with the
   parameter type directly — wrap them (`λ {u} {u'} → balance-∪ u u'` for the
   explicit-argument `module _ (utxo utxo' : UTxO)` provider, `λ {u} →
   outs-disjoint tx {u}`; UTxO's Σ-left-unique eta issue).  Check the provider's
   actual telescope — `Utxo.Properties.Base` switched `balance-∪` from implicit
   to explicit map arguments.

5. Force full elaboration by re-stating the consumer's headline theorem, with
   whatever hypotheses it carries on that branch (the batch-threading proof
   adds `FreshTxIds (UTxOOf s) (batchTxIds tx)`, both names imported from
   `Utxo.Properties.PoV`):

   ```agda
   _ : {Γ : LedgerEnv} {s s' : LedgerState}
     → PoolDepositsRegistered (CertStateOf s)
     → FreshTxIds (UTxOOf s) (batchTxIds tx)
     → Γ ⊢ s ⇀⦇ tx ,LEDGER⦈ s' → getCoin s ≡ getCoin s'
   _ = LEDGER-pov
   ```

6. `agda src/PoVWiringCheck.agda` (prefix `nix develop --command` when outside
   the Nix shell; about 17 s on a warm `_build/`).  Exit 0 = drop-in verified:
   `--safe`, zero postulates, and the open-parameter count is exactly the
   not-yet-discharged set.

7. **Delete the file** (and any stray `PoVWiringCheck.agdai`) before any
   commit; confirm `git status` is clean.  Keep the wiring snippet in the PR
   body's "Verified drop-in compatibility" section so the next session can
   rebuild the module quickly.

## Notes

- Re-run after ANY movement of either branch: base rebases routinely rewrite
  the parameter block's surroundings, and positional application means a
  reordered block would silently mis-wire if the types weren't distinctive.
- A provider lemma held inside a provider module that takes hypotheses (the
  `SUBUTXOW-PoV` pattern) still counts as discharging the parameter — the
  hypotheses simply surface in the wiring module's parameter list, making the
  residual obligations explicit and countable.
