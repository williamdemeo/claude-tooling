# fls web-environment setup

fls carries no committed Claude config (IOG decision), so Claude Code WEB
sessions on fls start bare: no toolchain, no skills, no CLAUDE.md. The
committed-config route used by agda-algebras/air is closed here; the
supported alternative is the web environment's **setup script**, which
runs inside the container, outside the repo — nothing is committed to fls.

`setup-script.sh` is that script — descended from the pre-removal
SessionStart hook archived at `../attic/dot-claude/`, upgraded with the
prefetch mechanics from fls PR #1255
(<https://github.com/IntersectMBO/formal-ledger-specifications/pull/1255>,
branch `claude/env-config-test-zheoxs`, July 2026). It:

1. installs Nix if absent, and configures the caches the fls flake
   expects (`cache.iog.io` + `cache.nixos.org`, with trusted keys),
   preserving any `NIX_CONFIG` the environment already set;
2. persists PATH for the session;
3. **realises the dev shell with a persistent gc-root**
   (`nix develop --profile ~/.cache/fls/devshell-profile "path:$PWD"
   --command true`) so later `nix develop` calls fetch nothing;
4. optionally installs William's global + fls skills and CLAUDE.md into
   the **container's** `~/.claude` (never the working tree, so nothing
   can leak into a commit or PR) — only when `CLAUDE_TOOLING_TOKEN` is
   provided.

## Hard dependency: the PR #1255 flake change

The sandbox's GitHub proxy scopes tarball fetches (`api.github.com` /
`codeload.github.com`) to the session's own repositories, so the
`github:` flake-ref shorthand 403s for every third-party input, public or
not. fls PR #1255's first commit re-declares the inputs as `git+https://…`
(identical `narHash`es — a pin-level no-op) which the proxy serves. Until
that half of the PR merges into fls master, **no setup script can resolve
the fls flake behind the proxy** — the toolchain phase of this script will
fail non-fatally and say so. Known follow-up recorded on the fls issue:
`nix flake update` re-introduces `github:` transitive nodes until a
durable fix exists.

## Why a setup script and not a SessionStart hook

Only the setup-script phase of a web environment is **snapshotted and
cached**: it runs for the first session, is reused by later *new*
sessions, is skipped on *resume*, and is rebuilt when the setup script or
allowed-hosts list changes (or on cache expiry, ~7 days). A SessionStart
hook re-runs every session and its work is never cached — the June hook
in `../attic/` was the wrong architecture for exactly this reason.

## Wiring it into the fls web environment (one-time, in the web UI)

1. Environment selector (cloud icon) → your fls environment → **Edit**.
2. **Network access**: **Trusted**, or a **Custom** list keeping the
   defaults plus `nixos.org`, `cache.nixos.org`, `cache.iog.io`,
   `github.com` (`None` guarantees failure).
3. **Setup script**: paste the contents of `setup-script.sh` (or, with
   the token below, fetch-and-run it from this repo).
4. **Environment variables** (all optional):
   - `CLAUDE_TOOLING_TOKEN` — fine-grained GitHub PAT, read-only
     *Contents* on `williamdemeo/claude-tooling` only; enables step 4.
   - `FLS_DEVSHELL_GCROOT` — override the gc-root profile path.
   - `FLS_WEB_SETUP_FORCE=1` — only if the script reports it refused to
     run because `CLAUDE_CODE_REMOTE` was unset during the setup phase.

Shallow-clone note for humans: web checkouts are shallow, and Nix's git
fetcher fails on them — if you run the shell by hand in a web session,
use `nix develop path:.` (as the script does) or `git fetch --unshallow`.

## Verification status (2026-08-10)

- Setup-script phase, caching lifecycle, and network-access levels:
  exercised on fls in July 2026 (PR #1255's testing) and documented at
  code.claude.com/docs (Claude Code on the web).
- Still unverified: whether `CLAUDE_CODE_REMOTE` / `CLAUDE_ENV_FILE` are
  set during the setup phase (the script handles both cases), and the
  claude-tooling fetch phase end-to-end (docs/terminal-vs-web.md,
  experiment iii).

## Future work

First-typecheck latency is dominated by the `_build` `.agdai` interface
cache, which this script does not populate; a setup script could also
restore the latest CI `_build` artifact (noted in PR #1255's README).
