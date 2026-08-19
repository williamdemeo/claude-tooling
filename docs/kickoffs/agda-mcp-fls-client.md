<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-8-agda-mcp-fls-client.md
     (authored 2026-08-16 for agda-native-air issue #103). Launch a fresh
     session from the air issue worktree with:
     Read and execute `~/claude-kickoff-prompts/kickoff-8-agda-mcp-fls-client.md` -->

# Kick-off: agda-mcp for fls sessions (agda-native-air issue #103)

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt, the referenced paths, and the issue —
read it in full first (`gh issue view 103`). Push back where the design
seems wrong; William explicitly wants that. Nothing mutates the fls
checkout or any live config without his explicit yes.

## Mission

agda-algebras sessions drive agda-mcp daily; fls sessions have nothing —
and never did (verified 2026-08-16: no `.mcp.json` in the fls tree, its
history, or archived config). Produce a TESTED MCP registration that lets
a Claude session in an fls checkout typecheck fls modules through
agda-mcp, using **fls's own pinned agda** — never this repo's — so IOG's
version pins stay authoritative.

## Where you are

- Repo: `formalverification/agda-native-air`, in a worktree William
  created off the issue branch (main checkout:
  `~/git/formalverification/agda-native-air/main`; worktrees beside it).
  Small commits, PR to `main`, William reviews and merges.
- Load-bearing skills in your set: `driving-agda-mcp` (the JSON-RPC stdio
  transport — your verification instrument, zero API cost) and fls's
  `agda-typecheck` (how fls actually typechecks: `nix develop --command
  agda <module>`; the flake pins agda + agda-sets, agda-stdlib-classes,
  agda-stdlib-meta, standard-library).
- The fls checkout you test against: `~/git/IO/fls/master` (IOG repo —
  it must never end up dirty; normal agda build artifacts are fine).

## Measured facts (2026-08-16 — re-measure, don't trust)

- `agda-mcp` already has the escape hatch: `--agda-bin PATH` (app/Main.hs;
  default "agda"). Also relevant: `--agda-flags`, `--timeout` (default
  300s; fls modules can be slower), `--check-command`/`--check-timeout`
  (the #78 project gate), `--verbose`.
- `scripts/run-server.sh` enters THIS repo's backend shell and anchors
  cwd/AGDA_NATIVE_AIR_ROOT here (the #76 fix) — so with `--agda-bin` the
  backend shell hosts only the server runtime while the checking agda is
  the client's. That split is the whole design.
- The agda-algebras registration is the shape to imitate
  (claude-tooling `projects/agda-algebras/mcp.json`): command =
  run-server.sh, args carry the per-project configuration.
- No realised fls devshell profile exists locally
  (`~/.cache/fls/devshell-profile` is absent) — William typechecks via
  plain `nix develop`. The web-provisioning mechanics
  (`nix develop --profile <gc-root> "path:$PWD" --command true`) are in
  claude-tooling `projects/fls/web-environment/setup-script.sh`.

## The work (the issue's four open questions, in dependency order)

1. **A stable path to fls's agda.** Candidates: (a) realise a local
   gc-root profile with the web-provisioning mechanics and use
   `<profile>/bin/agda` — FIRST verify agda actually lands in the
   profile's bin; (b) resolve the store path once
   (`nix develop --command which agda`) — silently stale after a flake
   update, so if chosen, say how staleness gets caught; (c) a tiny exec
   wrapper running agda through `nix develop --command` — viable only if
   agda-mcp holds ONE persistent agda process per server (measure: does
   it spawn per request?). Recommend one with tradeoffs.
2. **Protocol compatibility.** Drive the server over stdio
   (`driving-agda-mcp`) with `--agda-bin <fls agda>` and run
   `check_file`, `get_diagnostics`, `get_goal` against a REAL fls module
   (a small one first, e.g. something under `src/` that the
   `agda-typecheck` skill would check). fls's pinned agda version may
   predate what agda-mcp's interaction driver expects — if it breaks,
   that becomes the real issue-#103 work; report before fixing.
3. **Flags.** `agdaWithPackages` may bake the library set into the
   wrapped agda, making `--agda-flags` empty. Measure with a module that
   imports the pinned libraries; add only what fails.
4. **Hygiene.** After a full test run, `git -C ~/git/IO/fls/master
   status` must show nothing beyond artifacts fls's own gitignore covers.
   The #76 pollution class is guarded in run-server.sh — re-verify from
   an fls cwd anyway.

## Verification discipline

- Everything above costs ZERO Anthropic tokens: stdio transport for the
  server, `claude mcp list` for config resolution. For `claude mcp list`,
  test from a SCRATCH git fixture containing the candidate `.mcp.json` —
  do NOT drop `.mcp.json` into the fls working tree (fls's exclude file
  has no `/.mcp.json` line yet; the real link arrives via claude-tooling
  post-merge, which also adds the exclude line).
- A wrong timeout looks like a protocol failure. Time a plain
  `nix develop --command agda <module>` run first so you can tell them
  apart.

## Deliverable (end your final message with these)

1. The tested registration JSON — the exact content for claude-tooling's
   `projects/fls/mcp.json` — plus the evidence: which fls module was
   checked, through which agda binary, in how long.
2. Any air-side changes as a normal PR on this repo (William-gated).
3. The deployment one-liner for William, to run in claude-tooling AFTER
   he adds that file there: `make install PROJECT=fls` then, from an fls
   checkout root, `claude mcp list`. (Sessions never request PR reviews,
   and the claude-tooling side is William's/its own session's — hand it
   off, don't do it.)

## Working style

Small commits; the authorship/attribution standing orders in your loaded
CLAUDE.md apply. For design forks (the stable-path decision above),
present options with a recommendation and let William choose.
