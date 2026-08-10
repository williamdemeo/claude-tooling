# fls attic

Historical fls Claude config kept for reference.  Nothing under `attic/` is
deployed, linted, or touched by install.sh.

## dot-claude/ — snapshot of the config kept out of the fls repo

Verbatim copy (2026-08-09) of `~/git/IO/fls/dot-claude/`, a working dir
dated 2026-06-29/30.  An older revision of the same three files is tracked
on branch `claude/agda-skill-and-session-hook` (local and origin); the
committed-config route was abandoned for fls (IOG repo) and the live setup
became the parent-level `.claude/` now managed by this repo.

+  `hooks/session-start.sh` — the NEWEST revision anywhere of the fls
   provisioning hook (the branch copy is ~13 lines older): installs Nix,
   configures `cache.iog.io` + `cache.nixos.org` substituters with the IOG
   trusted key, persists PATH via `CLAUDE_ENV_FILE`, pre-warms
   `nix develop`.  It documents the network-policy blocker (nixos.org and
   cache.iog.io returned 403 in web containers as of 2026-06-16) and the
   allowlist fls needs: `nixos.org`, `cache.nixos.org`, `cache.iog.io`,
   `github.com`.  NB the header says it also serves terminal sessions
   launched outside a Nix shell, but the `CLAUDE_CODE_REMOTE` guard makes
   it web-only as written.
   **Why kept**: provenance.  The living, adapted version is
   `../web-environment/setup-script.sh` (wired into the fls web
   environment configuration, not the repo); this dir preserves the
   original hook verbatim.
+  `settings.json` — SessionStart wiring for the hook (same shape as the
   agda-algebras / agda-native-air ones).
+  `skills/agda-typecheck/SKILL.md` — the ORIGINAL fls-specific typecheck
   skill; identical to the branch copy, superseded by the generalized
   `projects/fls/claude/skills/agda-typecheck/` that is live today.
