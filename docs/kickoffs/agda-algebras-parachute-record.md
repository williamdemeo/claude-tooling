<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-9-agda-algebras-parachute-record.md
     (authored 2026-09-04 for agda-algebras issue #572). The worktree
     ~/git/ualib/agda-algebras/worktrees/572-flrp-parachute-modules-improvements
     exists on the branch of the same name (from origin/master, pushed), with
     its claude-tooling links in place. Launch `claude` from that root, inside
     `nix develop` entered there: the agda-mcp registration expands `${PWD}`
     at launch, and the flake's shell hook writes the worktree's own `agda`
     wrapper onto PATH. Then:
     Read and execute `~/claude-kickoff-prompts/kickoff-9-agda-algebras-parachute-record.md` -->

# Kick-off: a `Parachute` record for agda-algebras (issue #572)

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt, the referenced paths, and the issue.
Push back where the design seems wrong; William explicitly wants that, and
Step 3 below is where you do it.

You are working in the ualib/agda-algebras repository on GitHub issue #572,
"[FLRP] Parachute modules: implicit canopy index, prose pass, and a
`Parachute` record with the lattice it presents".  Start by reading the
issue itself (`gh issue view` errors against this repository's classic
Project, so use `env -u GH_TOKEN gh api repos/ualib/agda-algebras/issues/572`).
It describes a commit of parachute-module improvements that was made during
the review of PR #534 and committed to that PR's branch by mistake, lists the
loose ends visible in that commit's diff, and proposes one further
improvement: a record type `Parachute` packaging the five-parameter telescope
that now appears in four module headers, together with a function from a
`Parachute` to the lattice it presents.  Then read the commit's full diff
(`git show e8839187`), the design note `docs/notes/flrp-rp1-parachutes.md`
§ 2 (especially § 2.4 and § 2.5, which the issue's design constraints come
from), and the four modules the telescope occurs in:
`Classical.Structures.Lattice.Parachute`, `FLRP.Parachute.Representation`,
`FLRP.Parachute.Theorems`, and `FLRP.Reductions`.

Do the work in four steps, in this order.

## Step 1: where you are

You should be at the root of the worktree
`~/git/ualib/agda-algebras/worktrees/572-flrp-parachute-modules-improvements`,
on the branch of the same name (created from `origin/master`, which it
tracks), inside `nix develop` entered from that root.  Verify all of this
before doing anything else: `git rev-parse --show-toplevel` and
`git rev-parse --abbrev-ref HEAD` name that worktree and branch,
`command -v agda` prints that worktree's `.agda/bin/agda` (the flake's shell
hook writes it on entry), and `.claude` and `.mcp.json` at the root are
symlinks.  If any of these fails, stop and say so rather than working around
it: a session launched elsewhere has the wrong `agda` on `PATH` (the wrapper
hard-codes the library file of the checkout the shell was entered from, so
other checkouts resolve modules to the wrong tree) and an agda-mcp server
registered on the wrong checkout.  Should only the wrapper be missing,
`nix develop --command bash -c 'command -v agda'` run at the worktree root
writes it and prints its path.

The repository uses one git worktree per branch under
`~/git/ualib/agda-algebras/worktrees/`; the main checkout
`~/git/ualib/agda-algebras/master` is only for fetching and for
`git worktree add`.  Work only inside this worktree.  Every type-check goes
through the wrapper: `make check` for the library and
`agda src/Path/To/Module.lagda.md` for one module both resolve to
`./.agda/bin/agda`; `make AGDA=./.agda/bin/agda check` says so explicitly.

## Step 2: move the commit

Commit `e8839187` ("fixed many things overlooked by previous sessions") is
the head of branch `510-m6-18-minimal-normal-subgroups`, the branch of PR
#534, whose worktree is
`~/git/ualib/agda-algebras/worktrees/510-m6-18-minimal-normal-subgroups`; its
parent `8aea69db` is the CI-green state the PR should return to.  The commit
has been checked to cherry-pick onto `master` with no conflicts.  Cherry-pick
first and remove it from the PR branch only afterwards, so that the commit is
never unreachable:

1. In this worktree, run `git cherry-pick e8839187`, then
   `git commit --amend` with a message that says what the commit does (the
   issue's first section is an accurate summary; keep the author as is, and
   add no AI trailer of any kind).  Confirm `make check` passes on the result
   before touching the PR branch.
2. Confirm the #534 worktree is clean (`git -C <that worktree> status --short`
   prints nothing) and that its head is still `e8839187`; then run
   `git -C <that worktree> reset --hard 8aea69db` and
   `git -C <that worktree> push --force-with-lease=510-m6-18-minimal-normal-subgroups:e8839187 origin 510-m6-18-minimal-normal-subgroups`.
   Verify that `git log origin/510-m6-18-minimal-normal-subgroups -1 --oneline`
   shows `8aea69db`.
3. Leave a short comment on PR #534
   (`env -u GH_TOKEN gh api repos/ualib/agda-algebras/issues/534/comments -f body='...'`)
   saying the commit moved to the branch of #572 and why.

Never use bare `git stash` in this repository: the stash stack is shared
across all worktrees.

## Step 3: weigh the design before implementing it

The issue proposes a *record of families*: `record Parachute (m : ℕ)` whose
five fields are the telescope verbatim (`𝓛 : Fin (suc m) → Lattice α ρ`,
`𝒕 : ∀ {i} → TopOf (𝓛 i)`, `top?`, `𝒃`, and `nondeg`), `LatticeParachute`
re-parameterized by one `(𝒫 : Parachute m)` with `open Parachute 𝒫` at the
top of its body, and a top-level function of type
`Parachute m → Lattice (α ⊔ ρ) (α ⊔ ρ)`.  Its virtue is a minimal diff: the
module body and the implicit-index style the commit introduced are
untouched, and the consumers change only their headers.

William wants this proposal examined, not just executed.  Weigh at least the
*family of records* alternative: a per-canopy record (a lattice with a
chosen top and bottom, a decidable top test, and a proof that the ends
differ; the library does not yet name that notion, `TopOf` and `BottomOf` of
`Classical.Properties.Lattice` are its Σ-shaped ingredients, and the only
bounded-lattice bundle in use is the standard library's order-theoretic one,
in `Classical.Structures.Group.NormalSubgroupLattice`), with
`Parachute m = Fin (suc m) → Canopy α ρ`.  That shape makes the `Mᵃ` family
of `FLRP.Reductions` a constant family over one `chain₂` canopy value
(bundling `chain₂-lattice`, `chain₂-top`, `chain₂-bot`, and the private
`chain₂-top?` and `chain₂-nondeg`), and makes `BigCanopyᴸ i` a property of
`𝒫 i`; it costs a new library notion that "one canonical form per concept"
obliges you to relate to the existing bundles.  Consider any further shape
you find better.  Judge them on the following: § 2.5 of the design note (no
module application layered over `LatticeParachute`, so a wrapper module is
out); what unification sees once record projections replace variables (the
implicit inference of the canopy index must keep working as the commit set
it up); the module's type-checking cost, measured (§ 2.4 records about 6 s);
how the three FLRP consumers and the `Mᵃ` instance read afterwards; level
polymorphism over `Lattice α ρ` with the FLRP consumers at `0ℓ`; and the
corpus-quality goal of legible, stable definitions.

Write the comparison up briefly, with a recommendation, and post it as a
comment on issue #572.  If it favours William's proposal, say so and
proceed.  If it favours another shape, present the case to William in the
session and wait for his choice before implementing; the public shape of
these modules is his decision.

## Step 4: the record, the function, and the loose ends

Implement the chosen design: the record in
`Classical.Structures.Lattice.Parachute`, `LatticeParachute` parameterized
by it (one module, not two), the top-level lattice-of-a-parachute function
with the prose block ADR-010 asks for, the record threaded through
`ParachuteRep`, `ParachuteTheorems`, `Parachutes`, and `Compose`, `Mᵃ`
rebuilt as a value of the record, and the loose ends the issue lists tidied.
Profile `Classical.Structures.Lattice.Parachute` with
`agda --profile=internal` before and after: the module checks in about 6 s
today and must not regress (the `agda-typecheck-performance` skill explains
how to read the breakdown).  Update the design note (§ 2.2 and § 2.5) and
the module prose to describe the record, and record the design decision and
the alternatives weighed in the note.

## Conventions and gates

Every module is literate Agda (`.lagda.md`, per ADR-004) with the
`--cubical-compatible --exact-split --safe` options; match the surrounding
style and the project `CLAUDE.md` (implicit and explicit arguments as the
commit set them, named lemmas rather than `with`, `proj₁`/`proj₂`, kramdown
spans for inline Agda names, `+` bullets and two spaces after
sentence-ending periods in prose, no em-dash joining two sentences).  Try the
agda-mcp server first for hole-driven drafting, as the project `CLAUDE.md`
requires, and end the session with the field report it asks for.  The gates
before a PR are `make check`, `make unused-imports`, `make check-links`, and
`make docstrings`; the work is not done until all four pass.

When finished, push the branch (it already tracks its origin branch) and
open a PR against `master` that references #572, with a description in the
repository's style (one source line per paragraph and per bullet, `+`
bullets, no hard wraps), ending with a provenance line naming the actual
model, e.g. `🤖 AI-assisted development: Claude Fable 5 (Anthropic)`; never
add a `Co-Authored-By` trailer.  Do not request a review, and do not merge.
If PR #534 merges while you work, rebase onto the new `master`; the two
branches touch `FLRP.Reductions` in different places.
