# Recovery runbook: fresh machine → working Claude setup

This repo must work with git, a POSIX shell, and python3 ≥ 3.11 (stdlib
only) — no flake, no package manager steps — precisely because it is the
thing you reach for during recovery. All the logic is `scripts/ct.py`; the
`*.sh` entry points are two-line shims into it. 3.11 is the floor because
`tomllib` parses `projects.toml`.

1. **Install Claude Code and log in** (`claude` on PATH; `claude
   --version` sanity check). Not managed here. Check the interpreter in the
   same breath: `python3 --version` must report 3.11 or newer.
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

3. **Deploy** — via the shims, so nothing beyond `sh` and python3 is needed:

        cd ~/git/williamdemeo/claude-tooling/main
        ./install.sh          # idempotent; fresh machine ⇒ no --force needed
        scripts/check.sh      # static: everything ✓, zero pending

   (`make install` / `make check` run the same commands; the Makefile — and
   the bash its recipes use — is an everyday convenience, not a recovery
   requirement.)

4. **Prove it live (optional, costs a few haiku calls):**

        scripts/probe.sh             # skills + CLAUDE.md markers per location
        scripts/verify-discovery.sh  # only if discovery behavior itself is in doubt

5. **Not (yet) recovered by this repo** — restore by hand:
   - credentials (`claude` login), user-scope MCP servers (`~/.claude.json`
     — project-root `.mcp.json` files ARE recovered, from
     `projects/<p>/mcp.json`), auto-memory dirs and transcripts under
     `~/.claude/projects/` (back those up separately if they matter)

New worktrees afterwards: `scripts/link-worktrees.sh <project>` — see
docs/worktree-workflow.md.
