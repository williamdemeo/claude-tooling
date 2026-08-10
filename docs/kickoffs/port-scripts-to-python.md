<!-- Versioned source of the deployed kickoff prompt
     ~/claude-kickoff-prompts/kickoff-5-port-scripts-to-python.md
     Launch a fresh session with:
     Read and execute `~/claude-kickoff-prompts/kickoff-5-port-scripts-to-python.md` -->

# Kick-off: port the claude-tooling scripts to Python

You are starting fresh, with no memory of the sessions that designed this.
Everything you need is in this prompt, the repo, and GitHub issue
williamdemeo/claude-tooling#1 (same content as this prompt's Mission and
Acceptance sections; the issue is the tracked work item — reference it in
the PR with "Closes #1"). Push back where anything seems misguided —
William wants that.

## Where you are

Repo: `williamdemeo/claude-tooling` (PRIVATE), the versioned source of
truth for William's Claude Code config. Main checkout:
`~/git/williamdemeo/claude-tooling/main`. **`main` is LIVE-DEPLOYED**:
symlinks from `~/.claude` and from project parent dirs point into its
working tree (content under `global/` and `projects/` — do not rename
those paths). Convention: dev branches live in worktrees under
`~/git/williamdemeo/claude-tooling/worktrees/<branch>` — create one from
main (`git worktree add -b port-to-python ../worktrees/port-to-python`)
and do ALL work there; `main` must not change until the PR merges.
Read `README.md`, `docs/architecture.md`, and `docs/migration.md` first;
`make help` lists the targets.

## Mission

Port the shell tooling — `scripts/lib.sh`, `install.sh`,
`scripts/{link-worktrees,add-project,check,list,probe,verify-discovery}.sh`
(~900 lines) — to ONE typed, stdlib-only Python module with subcommands
(suggested: `scripts/ct.py`), folding `scripts/lint-skills.py` in as a
subcommand. Motivation (from #1): a real `set -e` function-return bug
already shipped once; probe.sh's `comm`-based set logic is unreadable;
`tomllib` (py ≥ 3.11) replaces the bespoke awk TOML-subset parser so
`projects.toml` becomes real TOML with no subset caveats.

**Interface freeze** (hard requirement — runbooks/docs must stay true):

- Same entry points: keep `install.sh` and the `scripts/*.sh` names as
  2-line exec shims into `ct.py` (docs and muscle memory reference them),
  or route the Makefile targets directly — but the documented commands
  (`./install.sh --dry-run --force fls`, `scripts/link-worktrees.sh fls`,
  `make check PROJECT=…`) must keep working verbatim.
- Same flags: `--dry-run`, `--force`, positional `global|<project>`
  filters; `CLAUDE_PROBE_MODEL` env for probe/verify.
- Same output vocabulary: `✓` ok, `→` planned (dry-run, counted
  separately), `!` expected/transitional warning, `!!` NEEDS ATTENTION
  (collected and recapped VERBATIM in a "NEEDS ATTENTION" section at the
  end — its absence is the user's green light), `✗` hard error. Colors off
  when not a tty or NO_COLOR is set. Exit nonzero ONLY on hard errors.
- Python stdlib ONLY (`tomllib`, `pathlib`, `subprocess`, `argparse`,
  `dataclasses`, `re`, …). Floor: python ≥ 3.11 — document it in
  README.md and docs/recovery.md; update docs/architecture.md's
  bash-constraint design bullet and projects.toml's header comment
  (real TOML now; keep the no-'#'-in-values caveat only if you keep any
  line-based fallback, which you should not).

## Quality bar (judged on maintainability, not just parity)

- Typed throughout (mypy-clean annotations); dataclasses for the manifest
  and per-item results; docstrings on every subcommand and non-obvious
  function. William's house style: functional-leaning, total functions,
  no hidden state, comprehensions where clearer than loops.
- ONE small module; resist over-abstraction — the interface freeze and
  the behaviors list below are the spec, not an invitation to build a
  framework.
- Add a small stdlib `unittest` suite for the pure logic (manifest
  parsing, link classification, lint regexes, probe expectation sets)
  plus a `make test` target (new targets are fine; documented ones are
  frozen). Tests must NEVER touch live config — tmp fixtures only.
- Suggested session config: a strong model (Opus-class or above) at high
  or max effort — this is design-dense one-shot work worth the
  deliberation.

## Behaviors that MUST survive (the bash encodes these; test for them)

1. `ensure_link`: correct symlink → ok; wrong symlink → silently re-point
   with the old target logged (comparison is STRING equality of
   `readlink`, targets are absolute); real file/dir → `!!` skip unless
   `--force`, which MOVES the original to
   `~/.local/state/claude-tooling/backups/<timestamp><absolute-path>`
   before linking; absent → create (mkdir -p the parent).
2. `ensure_realdir`: symlink pointing INTO this repo → replaced by a real
   dir (legacy whole-dir scheme); foreign symlink → `!!` unless --force;
   plain file → error; absent → mkdir.
3. **Tracked-`.claude` guard**: a checkout where `git -C <wt> ls-files
   .claude` prints anything is NEVER touched, even under `--force`
   (transitional repos, pre-removal-PR) — warn and skip.
4. Worktree enumeration ONLY via `git worktree list --porcelain` run in
   `<parent>/<main>` (lines starting `worktree `); registered paths may
   be missing on disk → warn ("stale entry; consider git worktree
   prune") and skip; the main checkout is in the list and gets the same
   root `.claude` link.
5. Exclude line: resolve the shared git dir via `git rev-parse
   --git-common-dir` from the main checkout (make it absolute), append
   `/.claude` to `<common>/info/exclude` idempotently.
6. Parent `.claude` stays a REAL dir; `skills/<name>` are PER-SKILL
   symlinks; any other member of `projects/<p>/claude/` (hooks/,
   settings.json) is linked at top level; a `settings.local.json` in the
   repo copy is never linked (warn); `mode = "committed"` projects are
   never touched; global tier = `~/.claude/CLAUDE.md` + per-skill links
   under `~/.claude/skills/`.
7. `canonical_root` ([meta] in projects.toml): warn loudly when running
   from a different checkout than the manifest declares.
8. `check` layering: (a) manifest sanity; (b) repo hygiene — the lint
   plus an error if any `settings.local.json` is TRACKED in this repo;
   (c) install-state classification per expected link: ✓ linked /
   `!` pending (real file or absent — expected mid-migration) /
   ✗ broken (dangling or wrong-target symlink into the repo), plus
   orphan sweeps (depth-1 symlinks into the repo that dangle, dotfiles
   included) and per-project worktree counts. Errors ONLY for genuine
   breakage — check must stay green-with-warnings mid-migration.
9. Lint rules (now a subcommand): frontmatter `name:` == dir name,
   `description:` non-empty (warn if < 40 chars or no when-to-trigger
   cue); duplicate names within any ONE session's visible set (global +
   one project — the same name in two different projects is FINE); stale
   absolute paths in skill bodies (`~/…` or `/home/williamdemeo/…`,
   skipping tokens containing `<>*$…`, stripping trailing punctuation);
   session junk — SHAs via
   `\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b` plus PR/issue
   references; a line containing `lint-skills: ok` is exempt; warn when
   a managed CLAUDE.md lacks a visible `PROBE-MARKER: ` line.
10. `probe`: builds expectations from the repo, not hardcoded lists;
    asserts PRESENCE of managed skill names and ABSENCE of names unique
    to foreign projects (union of other projects' names minus own minus
    global) — NEVER exact-set equality (sessions always see harness
    skills we don't manage); asserts the scope's own marker ONLY if the
    live CLAUDE.md file already contains it (graceful pre-migration
    skip) and foreign markers' absence always. Sessions are spawned as
    `claude --model <model> -p '<prompt>' < /dev/null` with cwd = $HOME
    (global) or `<parent>/<main>`; the two prompts are exactly:
    "Output only the names of your available skills, one per line. No
    other text." and "Output every line of your context that contains
    the string PROBE-MARKER, verbatim. If there are none, output exactly
    NONE."
11. `verify-discovery`: throwaway fixture (store dir + project parent +
    git-init'd main + one linked worktree), per-skill symlink chain,
    SYMLINKED parent CLAUDE.md whose marker is a VISIBLE line — HTML
    comments are stripped from CLAUDE.md at injection (verified
    2026-08-09), which is exactly what this fixture guards.
12. `add-project`: refuses existing manifest names or repo dirs; appends
    a real-TOML stanza; scaffolds CLAUDE.md stub (with marker) +
    `claude/skills/.gitkeep`; prints next steps.

## Parity harness (run BEFORE swapping anything; paste results in the PR)

From the worktree, where both implementations coexist:

    for args in "--dry-run" "--dry-run --force global" \
                "--dry-run agda-algebras agda-native-air"; do
      ./install.sh $args            > /tmp/bash-out.txt  2>&1   # old
      python3 scripts/ct.py install $args > /tmp/py-out.txt 2>&1  # new
      diff /tmp/bash-out.txt /tmp/py-out.txt                    # expect: none
    done

plus `check` (identical classification lines and counts) and `list`
(identical inventory). Whitespace-only differences are acceptable;
anything else is a bug in the port. These runs are read-only against
William's REAL live config — never run a non-dry-run install from the
worktree (its links would point at the worktree, and `canonical_root`
will rightly warn).

## Acceptance (from issue #1)

1. Parity harness clean on all three argument sets + check + list.
2. `make check` green in the worktree; one live `make probe PROJECT=fls`
   green (a few haiku cents); `verify-discovery` green (a few more) if
   time permits.
3. Final commits swap the shims/Makefile and delete the ported bash
   bodies (`scripts/lib.sh` etc.); docs updated (README, architecture,
   recovery, projects.toml header). Small thematic commits; open a PR
   titled for the port with "Closes #1"; **William merges — do not
   merge, do not touch `main`, do not run non-dry-run installs.**
