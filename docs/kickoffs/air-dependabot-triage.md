<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-6-air-dependabot-triage.md
     Launch a fresh session with:
     Read and execute `~/claude-kickoff-prompts/kickoff-6-air-dependabot-triage.md` -->

# Kick-off: triage the agda-native-air Dependabot alerts

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt plus the repo. William approves every
merge and every alert dismissal; your job is triage, fixes, and evidence.
Push back where anything seems misguided — he wants that.

## Where you are

agda-native-air: `~/git/formalverification/agda-native-air/main` (main
checkout; dev branches go in worktrees under `../worktrees/`). It is a
polyglot research repo (Haskell backend, Scala driver + Spark ETL, Python
ml-pipeline, Agda harness) with a Nix flake toolchain. Claude guidance
loads from the parent-level CLAUDE.md (symlinked config; the committed
copy may already be removed — PR #90). Test entry points you will need:
`make ci-smoke` (four lanes; `CI_SKIP_ML=1` skips the Python lane — do
NOT skip it here) and the Python lane's own tests under `ml-pipeline/`.

## Snapshot (2026-08-13 — re-fetch, don't trust)

GitHub reports 14 open Dependabot alerts, ALL in
`ml-pipeline/python/requirements.txt` (pip ecosystem):

| sev | package | CVE | fixed in |
|-----|---------|-----|----------|
| HIGH | pyarrow | CVE-2026-25087 | 23.0.1 |
| HIGH | setuptools | CVE-2025-47273 | 78.1.1 |
| MED | setuptools | CVE-2026-59890 | 83.0.0 |
| MED | filelock | CVE-2025-68146 | 3.20.1 |
| MED | filelock | CVE-2026-22701 | 3.20.3 |
| MED | pytest | CVE-2025-71176 | 9.0.3 |
| MED | torch | CVE-2025-2998 | none |
| MED | torch | CVE-2025-2999 | 2.9.1 |
| MED | torch | CVE-2025-3730 | 2.8.0 |
| LOW | torch | CVE-2025-2148, -2149 | none |
| LOW | torch | CVE-2025-2953 | 2.7.1-rc1 |
| LOW | torch | CVE-2025-3000 | 2.13.0 |
| LOW | torch | CVE-2025-3001 | 2.10.0 |

Re-fetch with:

    gh api repos/formalverification/agda-native-air/dependabot/alerts \
      --paginate -q '.[] | select(.state == "open") | ...'

## Mission

Every alert ends this session either FIXED (version bumped, tests green)
or DISMISSED with a written reason William approved. Concretely:

1. Read `ml-pipeline/python/requirements.txt` first: which pins are exact
   and why. This is an ML pipeline; torch versions can affect
   training/eval reproducibility, so a torch bump is NOT a casual edit.
2. Triage each alert for reachability: most torch CVEs require loading
   untrusted models or serving; this pipeline loads its own artifacts.
   Low practical risk is a legitimate dismissal reason ("vulnerable code
   not reachable"), recorded per-alert.
3. Bump the easy wins (pyarrow, setuptools, filelock, pytest) to the
   fixed versions; decide the torch question deliberately (bump to the
   highest fixed-in that CI tolerates, or dismiss the no-fix CVEs with
   reasons).
4. Verify: run the Python lane tests and `make ci-smoke` (all lanes)
   inside the Nix shell exactly as CI does. Paste results in the PR.
5. One PR for the requirements bumps (single ecosystem, single concern —
   keep it that way per the repo conventions); dismissals go through
   `gh api -X PATCH .../dependabot/alerts/<n>` with
   `-f state=dismissed -f dismissed_reason=... -f dismissed_comment=...`
   only AFTER William approves the per-alert list.
6. Recommend (do not enact) repo-settings changes: enabling Dependabot
   security-update PRs so future alerts arrive as ready-made PRs.

## Hard rules

1. No major-version bumps without calling them out; no torch change
   without stating the reproducibility impact.
2. Tests are the gate: nothing lands unless the Python lane and
   `make ci-smoke` pass in the pinned Nix environment.
3. William merges the PR and approves every dismissal; batch your asks.
4. If `requirements.txt` turns out to be generated or constrained by
   something else (a lock, the flake, Spark image pins), STOP and present
   the real update path before editing.
