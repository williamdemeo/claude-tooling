# Claude Code: terminal vs web usage

**STATUS: interview stub.** Per the kickoff, this document's content comes
from interviewing William — it must not be invented. The questions below
are seeded with what the migration work established empirically; replace
this stub with the answers.

## What is already established (2026-08-09)

- Web sessions clone the repo into a fresh container: they see ONLY
  committed config — no `~/.claude`, no parent-dir CLAUDE.md, no symlinks.
  This is the architectural fault line between the two modes (see
  docs/architecture.md, "web-container exception").
- Both agda-algebras and agda-native-air carry elaborate committed
  SessionStart hooks whose sole purpose is provisioning Nix inside the web
  container (installer redirector domains, proxy/CA-bundle handling) —
  clearly actively used and iterated on.
- Web usage is visible in the worktree records: `claude/*` branches
  (random-name style) exist in fls (~9) and agda-algebras (~30).
- fls carries NO committed config (deliberately removed — IOG repo), so
  fls web sessions currently run bare.

## Interview questions for William

1. Which projects do you drive from the web UI, and roughly how often?
   Is web usage growing or shrinking relative to terminal?
2. For agda-algebras and agda-native-air: should web sessions keep full
   config (CLAUDE.md + skills + hooks)? That decides how much of the
   committed config the stage-4 removal PRs may actually remove
   (docs/migration.md, "the web-container conflict").
3. fls on the web: is running bare acceptable, or is it worth asking
   Carlos/IOG about a minimal committed CLAUDE.md?
4. Terminal habits worth documenting for future sessions: permission
   mode(s) you actually run, when you use background jobs, fast mode,
   effort levels, the `!` prefix, plan mode?
5. The kickoff-prompt convention (`~/claude-kickoff-prompts/`,
   `kickoff-N-….md`, "read and execute" openers): rules of thumb for when
   a task deserves a kickoff prompt vs a plain chat message?
6. Web-specific practices: how do you review/merge `claude/*` branches;
   do web sessions get different instructions; anything the committed
   hooks should additionally provision?
7. Anything you consider "best practice" that new sessions keep getting
   wrong?
