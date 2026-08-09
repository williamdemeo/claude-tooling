# Recovery runbook: fresh machine → working Claude setup

This repo must work with bash + coreutils + awk (+ python3 for the lint) —
no flake, no package manager steps — precisely because it is the thing you
reach for during recovery.

1. **Install Claude Code and log in** (`claude` on PATH; `claude
   --version` sanity check). Not managed here.
2. **Restore the layout contract.** Clone this repo to its canonical path:

        git clone git@github.com:williamdemeo/claude-tooling.git \
            ~/git/williamdemeo/claude-tooling/main

   Clone each project to the parent/main layout the manifest records
   (`projects.toml` is the authoritative list — today):

        ~/git/IO/fls/master                          (fls)
        ~/git/ualib/agda-algebras/master             (agda-algebras)
        ~/git/formalverification/agda-native-air/main
        ~/git/williamdemeo/williamdemeo.github.io/main
        ~/git/williamdemeo/github-project/main       (committed mode)

3. **Deploy:**

        cd ~/git/williamdemeo/claude-tooling/main
        make install          # idempotent; fresh machine ⇒ no --force needed
        make check            # static: everything ✓, zero pending

4. **Prove it live (optional, costs a few haiku calls):**

        make probe            # skills + CLAUDE.md markers per location
        make verify-discovery # only if discovery behavior itself is in doubt

5. **Not (yet) recovered by this repo** — restore by hand:
   - `~/.claude/settings.json` (model, effortLevel, permissions,
     `cleanupPeriodDays: 3650` — see docs/transcript-retention.md)
   - credentials (`claude` login), MCP registrations (`.mcp.json` files
     live in project repos), auto-memory dirs and transcripts under
     `~/.claude/projects/` (back those up separately if they matter)

New worktrees afterwards: `scripts/link-worktrees.sh <project>` — see
docs/worktree-workflow.md.
