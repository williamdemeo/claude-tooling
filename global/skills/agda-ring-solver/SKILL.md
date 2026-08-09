---
name: agda-ring-solver
description: Discharge tedious associativity/commutativity rearrangement lemmas in Agda equational proofs with the agda-stdlib reflective ring solver (Data.Nat.Tactic.RingSolver's solve-∀ and solve), instead of writing long ≡-Reasoning chains of +-assoc/+-comm/cong shuffles. Use whenever a proof needs a pure +/*-rearrangement over ℕ/Coin (or another commutative semiring), or when reviewing/simplifying such chains. Covers the two macros, --safe compatibility, and three pitfalls: type-class-wrapped operators (e.g. HasAdd._+_ in Ledger.Prelude / stdlib-classes) defeat the solver's syntactic matching; solve-∀ handles only visible ∀-binders; where-bound abbreviations cannot serve as solve atoms.
---

# Discharging arithmetic rearrangements with the ring solver

Long `≡-Reasoning` chains that only reshuffle `_+_` (associativity + commutativity,
no hypotheses) are pure commutative-semiring facts. The agda-stdlib reflection
frontend proves them in one line, keeping the *statement* (so surrounding chains
stay readable) and deleting the tedious proof.

## Availability

+ `Data.Nat.Tactic.RingSolver` (agda-stdlib ≥ 2.x) — pre-instantiated for ℕ
  (hence `Coin` in the ledger repos). Marked `--safe --cubical-compatible`; fine
  under a `--safe` fence.
+ For other carriers, instantiate `Tactic.RingSolver` with an
  `AlmostCommutativeRing` (see `ACR.fromCommutativeSemiring`).
+ **agda-stdlib-meta pinned at 2.3 (e.g. in formal-ledger-specifications) has NO
  ring solver** — its `Tactic/` tree ends at `Try.agda`. The stdlib-meta solver
  exists only upstream, newer than the pin. Check the nix store copy before
  planning around it; use the stdlib one instead.

## The two macros

```agda
open import Data.Nat.Tactic.RingSolver using (solve-∀; solve)

-- Closed goal, ALL binders visible:
swap-right : ∀ a b c → a +ᴺ b +ᴺ c ≡ a +ᴺ c +ᴺ b
swap-right = solve-∀

-- Variables already in scope (e.g. the lemma has implicit trailing binders,
-- or the equation lives inside a clause): list the atoms explicitly.
arithmetic-1 : ∀ a b c {d}{e}{f}{g}
  → a +ᴺ b +ᴺ c +ᴺ (d +ᴺ e +ᴺ f +ᴺ g) ≡ a +ᴺ b +ᴺ c +ᴺ d +ᴺ e +ᴺ f +ᴺ g
arithmetic-1 a b c {d}{e}{f}{g} = solve (a ∷ b ∷ c ∷ d ∷ e ∷ f ∷ g ∷ [])
```

## Pitfall 1 — type-class-wrapped operators (the big one)

The solver recognises the ring's operations **syntactically**. Projects using
agda-stdlib-classes overload `_+_` as a `HasAdd` method (`Ledger.Prelude`,
agda-algebras preludes, …). That method merely *reduces* to `Data.Nat._+_`; the
macro does not normalise the goal, so it treats `a + b` as one opaque atom and
fails with a confusing `Expr … !=< ℕ` unification error.

**Fix**: state the solver-facing lemmas with the raw operator, imported renamed:

```agda
open import Data.Nat.Base using () renaming (_+_ to infixl 6 _+ᴺ_)
```

Raw and overloaded `+` are definitionally equal, so lemmas stated with `_+ᴺ_`
discharge `_+_` goals **without any call-site changes**. Add a one-paragraph prose
note where you do this, so readers know why two spellings of `+` coexist.

## Pitfall 2 — `solve-∀` handles only visible binders

`solve-∀` intro-builds visible lambdas; a goal `∀ a b c {d} → …` fails to unify.
For lemmas with implicit trailing variables (kept implicit so call sites can let
the goal determine them), bind everything in the clause and use in-context
`solve` with the full atom list, as in `arithmetic-1` above.

## Pitfall 3 — `where`-bound abbreviations are not valid atoms

In-context `solve (O ∷ F ∷ …)` matches atoms syntactically against the goal.
`where`-bound abbreviations (`O = cbalance (outs tx)`) get inlined during
elaboration, so the listed atom `O` never matches. Generalise instead:

```agda
reshuffle : O + F + (P + S) ≡ O + (F + S) + P     -- abbreviation-spelled statement
reshuffle = go O F P S
  where
  go : ∀ o f p s → o +ᴺ f +ᴺ (p +ᴺ s) ≡ o +ᴺ (f +ᴺ s) +ᴺ p
  go = solve-∀
```

## Scope discipline

+ The solver proves single equations in `+`/`*`/literals only. Anything chaining
  hypotheses (`trans` over assumed equations, cancellation like `+-cancelʳ-≡`,
  facts about `⊖`/`posPart`/`∸`) stays a hand proof; replace only the pure
  rearrangement steps and keep the named lemma statements.
+ Prototype in a scratch project first (milliseconds vs. minutes): a directory
  with `scratch.agda-lib` containing `depend: standard-library` and a small
  `.agda` file exercising each goal shape; the in-repo nix `agda` resolves the
  pinned stdlib automatically. To test against the project's own prelude, put a
  throwaway module under `src/` instead — and delete it before committing.
+ Cost: each invocation adds reflection + normalisation time (~fractions of a
  second for linear goals with ≤ ~10 atoms); dozens of calls are fine.

## Worked example

`src/Ledger/Dijkstra/Specification/Ledger/Properties/PoV.lagda.md` in
formal-ledger-specifications (commit 475280d7f, PR #1203): thirteen rearrangement
lemmas converted, −133 lines, statements and chain structure unchanged.
