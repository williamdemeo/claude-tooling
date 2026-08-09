# Claude Code: terminal vs web usage

**STATUS: interview stub.** Per the kickoff, this document's content comes
from interviewing William — it must not be invented. The questions below
are seeded with what the migration work established empirically; replace
this stub with the answers.

## Research findings on skill distribution surfaces (2026-08-09)

From the official docs (code.claude.com/docs: web-quickstart, cloud-environments,
plugins, plugin-marketplaces, settings; support.claude.com articles
12512180 and 13119606):

- Web sessions use **"repo only" config** — committed CLAUDE.md and
  .claude/settings.json load; committed `.claude/skills/` presumably loads
  but is NOT explicitly documented (test it — experiment ii below).
- **Organization Skills** (claude.ai → Organization settings → Skills;
  Owner uploads a skill .zip) reach claude.ai chat/Cowork for all members.
  Docs say they do NOT reach Claude Code — but the web UI's environment
  configuration now shows a skills picker (Anthropic / organization /
  partners), which the docs don't describe yet. UI beats stale docs:
  verify empirically (experiment i).
- **Plugin marketplaces**: any git repo with `.claude-plugin/marketplace.json`
  can serve plugins that ship skills. `/plugin` is terminal-only; a
  committed `.claude/settings.json` with `enabledPlugins` (+
  `extraKnownMarketplaces`) may pre-activate plugins in web sessions —
  partially documented, unverified for private marketplace repos (the
  container needs credentials for a second repo).
- **Cloud-environment setup scripts** (documented) run inside the web
  container and CAN fetch skills into the container's `~/.claude/skills/`
  — a candidate for giving fls web sessions skills without committing
  anything to the IOG repo (needs the claude-tooling repo reachable from
  the container: PAT in environment env-vars, or public repo).

Pre-interview experiments only William can run (minutes each):

  i.  In the web env-config skills picker: do IOG org-uploaded skills
      appear? Is there an upload/add-custom path? Do personal
      (Customize → Skills) uploads show up?
  ii. Launch a web session on agda-native-air (committed skills present)
      and ask it to list its available skills — confirms/refutes
      "committed .claude/skills load on web".
  iii. If fls-web matters: try a cloud-environment setup script that
      clones claude-tooling (with a fine-grained PAT) — proves the
      container-fetch path.

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
