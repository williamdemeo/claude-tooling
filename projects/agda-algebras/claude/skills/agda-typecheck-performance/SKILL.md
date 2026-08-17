---
name: agda-typecheck-performance
description: Diagnose and fix slow-to-type-check Agda modules (this repository, or any Agda project). Use when a module, a library build, or CI is slow (`make check` takes too long, one module dominates a clean build, someone asks why a file is expensive, or you are asked to speed up type-checking). Covers profiling with `--profile=internal`, reading the phase breakdown, and the five fixes that actually move the needle.
---

# Making Agda type-check faster

**Measure before you touch anything, and profile before you guess.**  The intuition
"this proof is complicated, so it must be the typing" is usually wrong.  In the two
worked cases below, typing was 2 % and 36 % of the cost; the rest was coverage
checking, module instantiation, and serialization.  Both modules got 5–8× faster
with no change to the mathematics, and in both the fix was also a simplification.

## Step 1 — establish the baseline

Agda caches interfaces, so an unmodified module costs nothing.  Delete its interface
first, then time a standalone check:

```bash
# find the interface (location varies: _build/<version>/agda/... or beside the source)
find . -name 'MyModule.agdai'
rm -f _build/2.8.0/agda/src/Path/To/MyModule.agdai
time agda +RTS -M6G -A128M -RTS src/Path/To/MyModule.lagda.md
```

To rank the modules of a whole library, use `--profile=modules` on the aggregator
(`src/Everything.agda`) **from an empty build directory** — otherwise you time only
what happens to be stale.  That tells you *which* module to attack; it does not tell
you what to change.

## Step 2 — profile the phases

```bash
rm -f _build/2.8.0/agda/src/Path/To/MyModule.agdai
agda +RTS -M6G -A128M -RTS --profile=internal src/Path/To/MyModule.lagda.md
```

`--profile=internal` is the one that matters: it breaks the run into Typing,
Coverage, Serialization, Deserialization, InterfaceInstantiateFull, DeadCode,
Positivity, Termination.  Also useful:

+  `--profile=definitions` — attributes time to individual definitions.  Run it
   *after* `internal`, to find which proofs carry the phase you identified.  Beware:
   its `Miscellaneous` line absorbs everything not attributable to a definition
   (module application, serialization, dead-code analysis), and that line is often
   the largest one.
+  `--profile=modules` — per-module ranking, for whole-library work.  In this
   repository, `make profile` runs it over `src/Everything.agda`; override the
   mode with `make PROFILE=internal profile`.

Agda accepts **one** profiling mode per run (`--profile=internal --profile=modules`
is rejected), so measure twice rather than trying to combine them.

Verbosity flags of the form `-v profile:7 -v profile.definitions:15` (found in some
older Makefiles) silently produce no output on Agda 2.8; use `--profile=` instead.

**Subtract deserialization.**  When you check one module standalone, the
`Deserialization` line is the cost of loading everything it imports.  In a full
build that cost is paid once and shared, so it is *not* part of the module's
incremental cost.  Compare "total minus deserialization" against the per-module
number from `--profile=modules`; they should roughly agree.

## Step 3 — read the phase, pick the fix

| phase | what it is | usual cause | fix |
| --- | --- | --- | --- |
| **Coverage** | checking that clauses cover all cases | `with` / `rewrite` **inside a proof** | hoist the split into a named lemma taking the scrutinee as an explicit argument |
| **InterfaceInstantiateFull** | instantiating an applied module | `open SomeParamModule args public`, `module M = N args` — *or* `with` inside a nested parameterized module, since each `with` auxiliary re-abstracts the module telescope | merge the modules; remove the `with` (Fix 1) |
| **Serialization**, **DeadCode** | writing the `.agdai` | too many definitions, or definitions with huge types | fewer/smaller definitions; the two fixes above usually cut both |
| **Positivity** | datatype positivity | datatypes duplicated by module application | same fix as InterfaceInstantiateFull |
| **Typing** | actual type checking | genuinely hard unification, deep normalization | see "if it really is typing" below |

### Fix 1 — no `with` inside a proof (the big one)

A `with` abstracts the **whole goal** and generates an auxiliary function whose type
is the abstracted goal in the full context.  If the goal mentions anything that
unfolds into generic machinery — an algebra's interpretation function, a bundle
projection, a record of laws — coverage checking that auxiliary function is
extremely expensive, and you pay it once per `with`, per clause.

Instead, define the case analysis **once**, as a lemma whose scrutinee is an
explicit argument:

```agda
-- Slow: the split happens inside a proof whose goal is large.
foo : (i j : Fin n) → Big (f i j)
foo i j with i ≟ j
... | yes refl = …
... | no  _    = …

-- Fast: the split happens against a small goal, and consumers just apply it.
private
  foo′ : (i j : Fin n) (d : Dec (i ≡ j)) → Big (f′ i j d)
  foo′ i .i (yes refl) = …
  foo′ i j  (no _)     = …

foo : (i j : Fin n) → Big (f i j)
foo i j = foo′ i j (i ≟ j)
```

This works because the operation being reasoned about (`f`) should itself be defined
by an auxiliary that takes the `Dec` explicitly.  Do that first; every proof then
becomes an application.  `rewrite` is `with`, so the same applies — and when a
`rewrite` is unavoidable (e.g. pinning `(i ≟ i) ≡ yes refl` via decidable-equality
UIP), confine it to one tiny lemma with a small goal and route everything through
that lemma.

Bonus: this is what most Agda style guides ask for anyway ("prefer named helper
lemmas over opaque `with`/`rewrite` chains"), so the fast version is also the
readable one.

### Fix 2 — do not `open … public` a large parameterized module

```agda
module Inner (a : A) (b : B) where …          -- 30 definitions

module Outer (a : A) (b : B) (c : C) where
  open Inner a b public                        -- re-instantiates all 30
```

Every definition of `Inner` is re-instantiated, re-serialized, and (for datatypes)
re-positivity-checked.  Prefer **one module with more parameters**.  The extra
generality of the layered version is usually theoretical — check whether any
consumer actually instantiates `Inner` alone before defending it.

### Fix 3 — share repeated subterms

Watch for the same non-trivial term elaborated several times in one `where` block:

```agda
-- Slow: the existential is recomputed for each projection.
i₀    = proj₁ (¬∀⟶∃¬ card _ (λ i → all? …) ¬h)
¬hj   = proj₂ (¬∀⟶∃¬ card _ (λ i → all? …) ¬h)

-- Fast: elaborate it once.
ex : _
ex  = ¬∀⟶∃¬ card _ (λ i → all? …) ¬h
i₀  = proj₁ ex
¬hj = proj₂ ex
```

Each repetition costs a full elaboration of a large term, and the profiler shows it
spread across several small definitions rather than as one hot spot — so look for
*clusters* of mid-sized definitions that mention the same subterm, not just for the
single most expensive name.  The same applies to a record destructured by `with`
several times: bind it once and project.

### Fix 4 — shrink the interface

Serialization and dead-code analysis scale with the number of definitions and the
size of their types.  Fixes 1 and 2 usually cut both by an order of magnitude
because they remove duplicated definitions and `with`-generated auxiliaries with
enormous types.  `private` does **not** help — private definitions are still
serialized; it is a scoping mechanism, not a size one.

### Fix 5 — if it really is typing

Only then look at the mathematics:

+  Make the expensive structure a **module parameter** rather than a projection of a
   record: goals that mention variables are inert, goals that mention
   `SomeBundle.op (f i)` re-normalize on every conversion check.
+  Replace hand-written equational reasoning over derived operations by a
   **derivation from a standard-library interface** where one exists.  Deriving is
   usually cheaper than proving, not more expensive.
+  Give explicit type signatures and explicit implicit arguments at the sites where
   the profiler shows unification churn (`Typing.CheckLHS.UnifyIndices`,
   `Typing.With`).

## When it does not finish at all: bisect, do not profile

`--profile=internal` prints nothing when the run dies of heap exhaustion, so a
module that *never finishes* needs a different method: **bisect the file**.  Copy the
module under a scratch name, truncate it after a candidate definition, and time that:

```bash
L=$(grep -n "#### Some heading" src/Path/To/Mod.lagda.md | head -1 | cut -d: -f1)
head -n $((L-1)) src/Path/To/Mod.lagda.md \
  | sed 's/module Path.To.Mod where/module Path.To.Scratch where/' \
  > src/Path/To/Scratch.lagda.md
time (timeout 300 agda +RTS -M6G -A128M -RTS src/Path/To/Scratch.lagda.md)
```

Halve until one definition separates "seconds" from "heap exhausted".  Two cautions
learned the hard way: `grep -n … | cut -d: -f1` breaks when the pattern matches twice
(always `head -1`), and a `_` in a test term can *itself* be the blowup — a
metavariable under a stuck `lookup` on a large literal vector sends the unifier
hunting — so pass arguments explicitly when probing.

## The cost is often the *use*, not the definition

The blowups below all share a shape: a definition that is cheap to check becomes
ruinous one line later, when something forces it.  Measured on the `A5` (carrier 60)
filter-ideal work of #530, where the verified prefix cost 9 s and a single further
application exhausted a 32 GB heap.

+  **`abstract` is scoped to the module, not the block.**  Its definitions stay
   transparent to everything else in the module that defines them, so wrapping an
   expensive proof in `abstract` next to its consumer changes nothing.  Sealing works
   across a module boundary; within one module use **`opaque`**, which is by-name.
   This is the single most misleading of the five — it looks like a fix and is not.

+  **`from-yes` is cheap to state, expensive to apply.**  Checking
   `p : P; p = from-yes d` needs only enough reduction to see `d` says `yes`.
   *Applying* `p` forces the proof term, which drags in whatever the decision's
   payload mentions.  A decision costing milliseconds at its definition can be
   unusable one line later, so watch for a `from-yes` result that is *applied* rather
   than merely passed along.

+  **A module application at concrete arguments re-instantiates the module.**  Writing
   a relation as `Coset._∼_ 𝒢 K K-sg` re-instantiates `Coset` — and everything
   `Coset` itself instantiates, e.g. `Algebra.Properties.Group` — once per concrete
   argument.  Write the relation out directly and consume the module's lemmas *once,
   generically*, inside an opaque block.

+  **Pattern-matching a `Σ` argument blocks reduction where laziness was wanted.**
   `f (K , K?) = …` forces its argument open; `f K = … proj₁ K … proj₂ K …` lets
   `f K` reduce while `K` stays stuck.  That is the difference between a goal that
   normalizes a concrete structure and one that does not.

The general lesson: for a large concrete instance, keep every *proof* opaque and every
*computation* transparent, and never let a goal mention a concrete bundle whose
laws are decision sweeps.  If that cannot be arranged, the structure is wrong — build
the object so the expensive bundle never enters the types (for a group action, e.g.,
build the unary algebra straight from the multiplication table rather than from a
`Group` value).

## Step 4 — verify the change

A performance change must not change the mathematics.

1.  The module type-checks, and so does everything downstream (check a consumer, not
    just the module).
2.  Run the full build gate (`make check` or equivalent).
3.  Re-run the same measurement, and report *before → after* with the phase table.
4.  Confirm the public interface is unchanged, or say exactly how it changed and
    update consumers in the same commit.
5.  If the fix was also a simplification (it usually is), say so — that is what
    makes it reviewable.

## Worked examples (agda-algebras, 2026-07)

`Classical.Structures.Lattice.Parachute` was the slowest module in the library at
~45 s.  Standalone check 88 s → 8.4 s; module cost ~47 s → ~6 s.

| phase | before | after |
| --- | --- | --- |
| Coverage | 15.6 s | 0.9 s |
| Serialization | 10.5 s | 1.0 s |
| InterfaceInstantiateFull | 10.1 s | 0.5 s |
| DeadCode | 5.7 s | 0.8 s |
| Positivity | 2.5 s | 0.3 s |
| Typing | 1.0 s | 1.5 s |

Two changes: every proof-level `with` became a named lemma on the `Dec` value
(Fix 1), and a second module that did `open FirstModule args public` was merged into
the first (Fix 2).  No mathematical content changed.  The suspected culprit before
profiling — an order-theoretic derivation of eight lattice laws through
`Relation.Binary.Lattice.Properties.Lattice` — turned out to cost under 40 ms, i.e.
0.1 % of the module.  **Profile first.**

`Setoid.Subalgebras.Subdirect.Finite`, same treatment, ~16.7 s → ~0.8 s of module
cost (standalone 24.3 s → 4.6 s):

| phase | before | after |
| --- | --- | --- |
| Typing (of which `Typing.With`) | 6.0 s (2.8 s) | 0.46 s (0) |
| Coverage | 4.7 s | 0.04 s |
| InterfaceInstantiateFull | 2.7 s | 0.01 s |
| Serialization | 1.8 s | 0.07 s |

Five `with`s became lemmas taking the `Dec` (or `⊎`) value as an argument — one of
them a *nested* `with` inside a `where` inside a doubly parameterized module, which
was 3.0 s on its own — and two repeated `¬∀⟶∃¬` applications were shared.  Note the
20× overall factor: when a module is slow, the cause is usually one anti-pattern
applied several times, not a diffuse cost, so the fix is usually cheap and local.

For non-dependent goals, `Data.Sum.Base.[_,_]′` eliminates a `⊎` scrutinee with no
helper at all:

```agda
foo = [ (λ eq → …) , (λ ∈f → …) ]′ (argmax-sel f ⊤ xs)
```
