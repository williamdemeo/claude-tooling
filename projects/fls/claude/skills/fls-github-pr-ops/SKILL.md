---
name: fls-github-pr-ops
description: gh-CLI procedures for tending PRs on IntersectMBO/formal-ledger-specifications — editing PR bodies when `gh pr edit` fails, replying to inline review comments, reading Copilot reviews including their suppressed notes, thread resolved-state via GraphQL, CI watching, and safe branch sync after someone rebases. Use when managing a PR's review cycle from the terminal.
---

# PR operations on the fls repo

## Editing title/body — `gh pr edit` is broken here
`gh pr edit` fails on this repo with a Projects-classic GraphQL deprecation
error. Use REST instead:

    gh api repos/IntersectMBO/formal-ledger-specifications/pulls/<N> \
      -X PATCH -f title='…' -F body=@body.md

When the user wrote or revised the body themselves: fetch it fresh
(`gh pr view N --json body --jq .body > body.md`), apply surgical string
replacements (a python one-liner that ASSERTS each occurrence count), and
PATCH back. Never regenerate the body wholesale over their revision.

## Review comments
All threads with resolved-state (REST does not expose `isResolved`):

    gh api graphql -f query='query { repository(owner:"IntersectMBO",
      name:"formal-ledger-specifications") { pullRequest(number: N) {
      reviewThreads(first: 100) { nodes { isResolved isOutdated path line
      comments(first: 10) { nodes { databaseId author { login } body } } } } } } }'

Reply to an inline review comment (creates a threaded reply):

    gh api repos/IntersectMBO/formal-ledger-specifications/pulls/N/comments/<databaseId>/replies -f body='…'

Copilot specifics: its login starts with `copilot`; the review verdict lives in
the review BODY (`…/pulls/N/reviews`), and below-threshold findings hide in a
`<details><summary>Suppressed comments</summary>` block there. Suppressed notes
have NO thread — after triaging/fixing, respond with a PR-level comment
(`gh pr comment`) citing commits.

## CI
After each push, background-watch: `gh pr checks N --watch --fail-fast`
(exit 0 = all green). `push-artifacts-to-branch` passing implies the Agda,
Haskell, and mkdocs builds all succeeded.

### Two CI systems — Hydra checks what GitHub Actions does not
Hydra posts its own `ci/hydra-build:packages.<pkg>.<system>` checks. GitHub
Actions can be fully green while Hydra is red, so always read the whole roll-up:

    gh pr view N --json statusCheckRollup \
      --jq '.statusCheckRollup[] | "\(.conclusion)\t\(.name)"'

The gap that bites: `formal-ledger-agda` runs a bare `nix build`, whose default
package is `formal-ledger` (the `src/` library only). The separate Agda library
in `formal-ledger-test/` is built by Hydra alone, as
`packages.formal-ledger-test.{x86_64-linux,aarch64-darwin}`.

Read a Hydra log (step index is the failing step named on the build page):

    curl -sL "https://ci.iog.io/build/<build-id>/nixlog/<step>/raw" | tail -40

Reproduce locally instead of guessing — `formal-ledger` substitutes from
cache.iog.io, so the test library then builds in seconds:

    nix build .#formal-ledger-test --no-link

### Two recurring breakages the green jobs miss
1.  Adding a field to a structure record under `src/Ledger/Core/Specification/`
    (e.g. `CryptoStructure`) breaks `formal-ledger-test`. Its
    `Test.LedgerImplementation` builds those records module-style, as
    `record { Implementation ; … }`, so a field with no counterpart in
    `module Implementation` surfaces as `[UnsolvedConstraints]` on a stuck
    instance plus `[UnsolvedMetaVariables]` at the `record` expression. Fix by
    adding the matching definition to that module.
2.  Changing an exported `*Step`'s signature needs the new type re-exported from
    `build-tools/static/hs-src/src/MAlonzo/Code/Ledger/<Era>/Foreign/API.hs`.
    The `hs / build` job compiles the library either way, so a missing
    re-export is invisible in CI and only bites consumers.

## Branch sync when history moved (rebases/rewrites are routine here)
Never pull; check patch-equivalence first:

    git fetch origin
    git cherry origin/<branch> HEAD    # every line '-' => all local commits are upstream
    git reset --hard origin/<branch>   # untracked files survive

The user often leaves intentional uncommitted tidy-ups in the worktree: commit
those as standalone commits in their name (no Claude co-author trailer) rather
than sweeping them into your own commits.

## Property-tracking gate
On tracking branches, before every push:
`python3 build-tools/scripts/scan_properties.py --check`
(catalog: `build-tools/properties.yaml`; the generated dashboard and issues
view live in `build-tools/static/mkdocs/docs/`).
