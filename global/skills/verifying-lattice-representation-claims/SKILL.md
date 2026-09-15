---
name: verifying-lattice-representation-claims
description: Check the computational claims in a universal algebra or lattice theory paper instead of taking them on trust - run the paper's GAP scripts, and recompute the congruence lattice of every UACalc .ua algebra and compare it with the lattice drawn beside it in the LaTeX source. Use when asked to review, clean up, cite, publish or reproduce the code and data behind such a paper (fin-lat-rep, UACalc/AlgebraFiles, agda-algebras), or whenever a .ua file or an old .g/.gap script is about to be pushed somewhere citable. Covers getting GAP without installing it, the index drift that silently breaks decade-old GAP scripts, identifying a small lattice from its covering relations without being fooled by cover counts, and pruning an exhaustive small-groups search.
---

# Verifying the computational claims in a lattice representation paper

A paper of this kind rests on two artifacts: GAP scripts that exhibit a lattice
as an interval in a subgroup lattice, and UACalc `.ua` files holding algebras
whose congruence lattices are the lattices drawn in the paper.  Both rot
quietly.  Measured in a 2026-09 session on `fin-lat-rep`: one of four GAP
scripts had stopped establishing anything at all, with no error, and the
published copy of the algebra file had an algebra whose congruence lattice was
not the lattice it was captioned with.  Recompute; do not read and believe.

## 1.  Get GAP without installing it

`gap` may be shell-aliased to something else entirely (it was aliased to
`git apply`), and `apt` needs root.  `nix` does not:

    nix --extra-experimental-features 'nix-command flakes' \
        shell nixpkgs#gap --command gap -q -b -A -o 4g script.g

The first run downloads about a gigabyte and takes several minutes; after that
it is instant.  The flags matter, as follows:

+  `-q -b` suppress the banner and prompts, so stdout is just your `Print`
   output;
+  `-A` skips autoloading packages, which is much faster and avoids XGAP;
+  `-o 4g` raises the memory ceiling.  `ConjugacyClassesSubgroups` on a group
   of order a few hundred will exceed the default.

End the script with `QUIT;` or GAP waits for input.  Run a long search with
`nohup ... &` and poll its output file, not in the foreground.

## 2.  Expect index drift in any GAP script older than a few years

The single most common failure.  Old scripts pick subgroups out by position:

    M11 := Representative(ccms[6]);
    K1  := MaximalSubgroupClassReps(M11)[4];   # PSL(2,11)

Those positions are **not stable across GAP versions**.  When they change the
script does not error; it goes on computing with the wrong subgroups and prints
plausible nonsense.  In the measured case `[4]` had become S5 rather than
PSL(2,11), and the script reported 5 maximal subgroups containing `H` where the
paper says 2.

Repair by selecting on the property that actually identifies the subgroup,
which is usually its order:

    K1 := First(MaximalSubgroupClassReps(M11), x -> Size(x) = 660);
    H  := First(MaximalSubgroupClassReps(K1),  x -> Size(x) = 55);

Then confirm with `StructureDescription`.  Note that `StructureDescription`
itself may print a different (isomorphic) decomposition than the paper does:
`SmallGroup(288,1025)` prints as `(C2 x C2 x C2 x C2) : (C3 x S3)` where the
paper writes `(A4 x A4) : C2`.  Check the order and the structure, not the
string.

Guard XGAP calls so a script runs headless:

    if IsBoundGlobal("GraphicSubgroupLattice") then ... fi;

## 3.  Recompute the congruence lattice of every `.ua` algebra

`conlat.py` beside this file reads a UACalc `.ua` file and computes the
congruence lattice of a unary algebra in it, by closing each pair `(a,b)` under
the operations and then join-closing the principal congruences:

    python3 conlat.py SmallLatticeReps.ua B28

It prints `|Con(A)|` and the covering relations, and checks the result against
a hard-coded target.  For a whole catalog, parse the paper's own TikZ instead
of hard-coding: each diagram is a run of `\node(k) at (x,y)[e]{};` and
`\draw(a)--(b);` lines, which give the covering relations directly, and the
algebra `B`*i* is compared with the lattice `L`*i* drawn beside it.  That sweep
caught the bad algebra and confirmed the other 28.

Check shapes first; it is cheap and catches truncation:

    for each op: len(values) == cardinality ** arity, and every value in range

## 4.  Identifying a small lattice: count atoms and coatoms, not covers

`IntermediateSubgroups(G,H)` returns `inclusions`, a list of covering pairs
`[i,j]` where `0` is `H` and `m+1` is `G`.  It is tempting to identify the
pentagon N5 as "3 intermediate subgroups and 5 covering pairs".  **That is
wrong**: the modular lattice `H < a < {b,c} < G` also has 3 intermediates and 5
covers.  Use atoms and coatoms:

    atoms   := Set(Filtered(r.inclusions, p -> p[1] = 0),   p -> p[2]);
    coatoms := Set(Filtered(r.inclusions, p -> p[2] = m+1), p -> p[1]);
    # N5 iff Length(atoms) = 2 and Length(coatoms) = 2
    #        and Length(Intersection(atoms, coatoms)) = 1

For anything larger, do a brute-force digraph isomorphism against the covering
relations read off the paper's TikZ.  Seven elements is 5040 permutations,
which is nothing.

## 5.  Searching the Small Groups Library without building subgroup lattices

Sweeping every group up to some order for an interval of a given shape is
dominated by `ConjugacyClassesSubgroups`, and the 2-groups are what kill it:
order 128 alone has 2328 groups and ran 15 minutes without finishing.  Do not
reach for a bigger machine.  Characterize the bottom of the interval instead.

+  **Take `H` core-free.**  If `N = Core_G(H)` then `[H,G]` is isomorphic to
   `[H/N, G/N]` and `G/N` is smaller, so a smallest example has
   `Size(Core(G,H)) = 1`.
+  **`H` is an intersection of two maximal subgroups**, whenever the target
   interval has two coatoms whose meet is the bottom (N5 and M3 both do).  The
   coatoms of `[H,G]` are maximal subgroups `B`, `C` of `G`, and their meet in
   the interval is `B` &cap; `C`.  So enumerate `B` over
   `MaximalSubgroupClassReps(G)` (conjugating the configuration lets you fix
   `B` up to conjugacy) and `C` over all maximal subgroups, and take
   `Intersection(B,C)`.  No subgroup lattice is ever built.

    maxes := Concatenation(List(ConjugacyClassesMaximalSubgroups(G), AsList));
    for B in MaximalSubgroupClassReps(G) do
      for C in maxes do
        H := Intersection(B, C);
        if Size(H) < Size(B) and Size(Core(G, H)) = 1 then AddSet(cand, H); fi;
      od;
    od;

That took a sweep of every group of order 3 to 216 from "does not finish" to
five minutes, and confirmed that `SmallGroup(216,153)` is the only group in
that range with a pentagon upper interval.

`AddSet` dedupes by equality, not by conjugacy.  If you want conjugacy classes,
say so explicitly with `RepresentativeAction(G, K, H) = fail`; a set of twelve
distinct subgroups turned out to be a single class.

## 6.  Before publishing a `.ua` file anywhere citable

Compare by **content hash across the whole upstream tree**, not by filename.  A
file can already be upstream under another name: `A4xA4sdpC2.ua` was
`Groups/A4xA4_sdp_C2.ua`, and `DoubleWinged2x2.ua` was
`Groups/PSL2-11_sdp_C2.ua`.  Then compare by algebra signature (cardinality
plus the set of operation tables) to catch the same algebra wrapped in a
different file.

Zenodo: a repository's **concept** doi always resolves to the latest archived
version; a **version** doi pins one snapshot.  Get both from the API, since the
landing page shows only one:

    curl -s https://zenodo.org/api/records/<recid> \
      | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["doi"], d["conceptdoi"])'

Cite the concept doi in a paper unless the exact snapshot matters.  Check
whether the latest archived version predates the fix you just made: in the
measured case the only archived version was ten years old and did not contain
the file at all, the directory having been added fourteen months after the tag.
Merging a fix upstream does NOT move the doi; only a new release does.

## 7.  When a Zenodo release comes back "Failed"

A GitHub release on a repository whose Zenodo link has lain dormant for years
fails with `{"errors": "401 Bad credentials"}` on Zenodo's releases page.  That
is a GitHub error, not a Zenodo one: Zenodo accepted the webhook, then called
back into the GitHub API with the OAuth token you granted it years ago, and the
token had expired.

Diagnose it from the delivery log before touching the release, because it tells
you which half broke:

    gh api repos/OWNER/REPO/hooks --jq '.[] | "\(.id) \(.active) \(.events|join(","))"'
    gh api repos/OWNER/REPO/hooks/<id>/deliveries \
      --jq '.[] | "\(.delivered_at) \(.event)/\(.action) \(.status) (\(.status_code))"'

`published ... OK (202)` means delivery worked and the fault is Zenodo's
callback; later `created`/`released` events returning 409 are normal duplicates.
A non-2xx on `published` would instead mean the hook itself is broken.

The fix is to re-authorize, not to re-cut: disconnect and reconnect GitHub at
`zenodo.org/account/settings/linkedaccounts/`, granting the **organization** as
well as the personal account, then confirm the repo toggle is still ON at
`zenodo.org/account/settings/github/` and press Sync now.  **Check whether it
self-healed before deleting anything** (measured: it did, with no re-cut):

    curl -sSL -o /dev/null -w '%{url_effective}\n' https://doi.org/<concept-doi>

Only if it has not, re-trigger by `gh release delete vX.Y.Z --cleanup-tag --yes`
and re-creating; Zenodo never retries a failed release on its own.

Finally, verify the archive rather than the listing.  Download what the concept
doi actually serves and recompute from it:

    curl -sSL -o a.zip "https://zenodo.org/records/<id>/files/<name>.zip?download=1"

Expect the auto-derived metadata to be wrong where the repo has no `LICENSE`
and no `.zenodo.json`: a release whose predecessors say GPL-2.0 came out
`cc-by-4.0`, and the author affiliation was scraped from the current GitHub
profile rather than the one on the earlier record.  Editing a published record's
metadata does not mint a new doi, so fix it in the browser afterwards.
