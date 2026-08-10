# fls web-environment setup

fls carries no committed Claude config (IOG decision), so Claude Code WEB
sessions on fls start bare: no toolchain, no skills, no CLAUDE.md. The
committed-config route used by agda-algebras/air is closed here; the
supported alternative is the web environment's **setup script**, which
runs inside the container, outside the repo — nothing is committed to fls.

`setup-script.sh` is that script (the living descendant of the
pre-removal SessionStart hook archived at `../attic/dot-claude/`). It:

1. installs Nix and configures the caches the fls flake expects
   (`cache.iog.io` + `cache.nixos.org`, with trusted keys);
2. persists PATH and pre-warms `nix develop`;
3. optionally installs William's global + fls skills and CLAUDE.md into
   the **container's** `~/.claude` (never the working tree, so nothing
   can leak into a commit or PR) — only when `CLAUDE_TOOLING_TOKEN` is
   provided.

## Wiring it into the fls web environment (one-time, in the web UI)

1. Open the fls environment configuration in Claude Code on the web.
2. **Network policy**: allow `nixos.org`, `cache.nixos.org`,
   `cache.iog.io`, `github.com`.
3. **Setup script**: paste the contents of `setup-script.sh` (or, if the
   UI takes a command, fetch-and-run it from this repo — needs the token
   below either way, since claude-tooling is private).
4. **Environment variables** (optional but recommended):
   - `CLAUDE_TOOLING_TOKEN` — fine-grained GitHub PAT, read-only
     *Contents* permission on `williamdemeo/claude-tooling` only. Enables
     step 3 (skills + CLAUDE.md).
   - `FLS_WEB_SETUP_FORCE=1` — only if the script reports it refused to
     run because `CLAUDE_CODE_REMOTE` was unset during the setup phase.

## Verification status (2026-08-09)

- Setup scripts for cloud environments are a documented feature
  (code.claude.com/docs → cloud environments); that they can populate the
  container's `~/.claude` is the research-verified injection path.
- UNVERIFIED until tried once (docs/terminal-vs-web.md, experiment iii):
  the exact env-config field shape, whether `CLAUDE_CODE_REMOTE` /
  `CLAUDE_ENV_FILE` are set during the setup phase (the script handles
  both cases), and whether the default network policy still blocks
  nixos.org / cache.iog.io.

After the first successful run, ask the web session to list its skills —
the fls four plus the global set should appear — and record the result in
docs/terminal-vs-web.md.
