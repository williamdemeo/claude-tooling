# formal-ledger-specifications — working conventions

Professional IOG work with Carlos Tomé Cortiñas. Self-review rigorously
BEFORE asking Carlos to review; nothing merges to master without approval.
Correctness over speed.

## Layout and git

- `~/git/IO/fls/master` always has master checked out; use it for fetch/pull
  and creating worktrees. Branch work happens in worktrees under
  `~/git/IO/fls/worktrees/` (William's in `…/william/`, branch names not
  prefixed; Carlos's in `…/carlos/`, usually `carlos/`-prefixed).
- New worktree ritual: `git worktree add -b <branch> ../worktrees/<branch>
  origin/<branch>`, then `ln -s ~/git/IO/fls/.claude <worktree>/.claude`
  (project skills live in `~/git/IO/fls/.claude/skills/`; the symlink is
  git-excluded repo-wide via master's `.git/info/exclude`).
- Branch histories get rebased/rewritten routinely: before any
  `git reset --hard origin/<branch>`, check `git cherry origin/<branch> HEAD`
  (every line `-` ⇒ nothing local is lost).
- Small commits with clear messages. Claude's commits carry the
  Co-Authored-By Claude trailer; William's own uncommitted tidy-ups found in
  the worktree get committed standalone, without the trailer.

## Libraries and code

- This repo depends on agda-sets, agda-stdlib-classes, and agda-stdlib-meta —
  their idioms are welcome HERE (William's personal repos deliberately avoid
  them; never assume conventions transfer between the two worlds).
- Module prose: Carlos's iterative-deepening style — plain-terms overview
  first, deepen in passes, echo structural points at the lemma site. Status
  talk ("proved in this PR", "recently added") belongs in PRs and issues,
  never in module prose.
- Typecheck any edited Agda before declaring work done (agda-typecheck skill).

## Property tracking

- Catalog: `build-tools/properties.yaml`. Status is DERIVED from the Agda —
  never declare it. The dashboard and issues view are generated into
  `build-tools/static/mkdocs/docs/`; edit the catalog, regenerate, commit
  together. Run `python3 build-tools/scripts/scan_properties.py --check`
  before every push that touches the catalog, property modules, or generated
  files.

## Claude config for this project

Source of truth: the williamdemeo/claude-tooling repo (projects/fls/),
symlinked into place — `~/git/IO/fls/CLAUDE.md` and the per-skill links
under `~/git/IO/fls/.claude/skills/` point there. Add or edit skills in
claude-tooling, then run `make install PROJECT=fls` there. Project skills
belong in that repo, not in `~/.claude/skills/`.

PROBE-MARKER: claude-tooling/fls
