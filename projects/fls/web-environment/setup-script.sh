#!/usr/bin/env bash
# projects/fls/web-environment/setup-script.sh
#
# Provision a Claude Code WEB container for formal-ledger-specifications
# work. fls carries no committed Claude config (IOG decision), so this
# script — wired into the fls web ENVIRONMENT configuration, not the repo —
# is how web sessions get a toolchain and (optionally) William's config.
#
# Descended from the pre-removal SessionStart hook preserved at
# ../attic/dot-claude/hooks/session-start.sh (this is the living version).
#
# What it does (all steps idempotent, all failures non-fatal):
#   1. install Nix (single-user) if absent
#   2. enable flakes; add the substituters the fls flake expects
#      (cache.iog.io + cache.nixos.org, with trusted keys)
#   3. persist PATH for the rest of the session
#   4. pre-warm `nix develop` so typechecking is fast
#   5. set William's git identity and silence Claude Code's commit/PR
#      attribution in the container (the authorship standing order:
#      commits are authored by William, never by an AI identity)
#   6. OPTIONAL: if CLAUDE_TOOLING_TOKEN is set, fetch williamdemeo/
#      claude-tooling and install the global + fls skills and CLAUDE.md
#      into the container's ~/.claude (never into the repo working tree,
#      so nothing can leak into a commit or PR)
#
# NETWORK POLICY the environment must allow:
#   nixos.org, cache.nixos.org, cache.iog.io, github.com
#   (as of 2026-06-16 the default policy 403'd nixos.org and cache.iog.io —
#   the script degrades gracefully and says so)
#
# ENVIRONMENT VARIABLES (set in the environment configuration):
#   CLAUDE_TOOLING_TOKEN   optional; fine-grained PAT, read-only Contents
#                          on williamdemeo/claude-tooling, for step 5
#   FLS_WEB_SETUP_FORCE=1  run even when the container heuristics fail
#                          (e.g. CLAUDE_CODE_REMOTE unset during setup)

set -uo pipefail

log() { printf '[fls-web-setup] %s\n' "$*"; }

# ---------------------------------------------------------------- guard --
# Never provision William's real machine by accident. Web sessions export
# CLAUDE_CODE_REMOTE=true; if the setup phase runs before that is set, put
# FLS_WEB_SETUP_FORCE=1 in the environment's env vars instead.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && [ "${FLS_WEB_SETUP_FORCE:-}" != "1" ]; then
  log "not a remote container (CLAUDE_CODE_REMOTE != true) and FLS_WEB_SETUP_FORCE != 1; refusing."
  exit 0
fi

# ---------------------------------------------------------- 1. nix install --
if ! command -v nix >/dev/null 2>&1 && [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.nix-profile/etc/profile.d/nix.sh"
fi

if ! command -v nix >/dev/null 2>&1; then
  log "installing nix (single-user)..."
  if curl -fsSL -m 30 -o /tmp/nix-install https://nixos.org/nix/install; then
    sh /tmp/nix-install --no-daemon --yes 2>&1 | sed 's/^/[nix-install] /' || \
      log "nix installer exited non-zero (continuing)."
    if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
      # shellcheck disable=SC1091
      . "$HOME/.nix-profile/etc/profile.d/nix.sh"
    fi
  else
    log "ERROR: cannot fetch https://nixos.org/nix/install (network policy likely blocks nixos.org)."
    log "       Allow nixos.org + cache.nixos.org + cache.iog.io + github.com in this"
    log "       environment's network policy; the script works as-is once they are allowed."
  fi
fi

if command -v nix >/dev/null 2>&1; then
  log "nix present: $(nix --version 2>/dev/null || echo unknown)"

  # -------------------------------------------------- 2. flakes + caches --
  mkdir -p "$HOME/.config/nix"
  NIX_CONF="$HOME/.config/nix/nix.conf"
  # Append via extra-experimental-features so an existing experimental-features
  # line is not clobbered; key the check on `flakes` specifically.
  grep -qE 'experimental-features.*flakes' "$NIX_CONF" 2>/dev/null || \
    echo 'extra-experimental-features = nix-command flakes' >> "$NIX_CONF"
  grep -q 'cache.iog.io' "$NIX_CONF" 2>/dev/null || cat >> "$NIX_CONF" <<'CONF'
substituters = https://cache.iog.io https://cache.nixos.org/
trusted-public-keys = hydra.iohk.io:f/Ea+s+dFdN+3Y/G+FDgSq+a5NEWhJGzdjvKNGv0/EQ= cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=
CONF
  # Also pass flakes via NIX_CONFIG, PRESERVING anything the environment
  # already set (a hand-rolled root single-user install needs
  # `build-users-group =` and `sandbox = false` there; the official
  # installer path above does not).  Mechanics from fls PR #1255.
  export NIX_CONFIG="experimental-features = nix-command flakes${NIX_CONFIG:+
$NIX_CONFIG}"

  # ----------------------------------------------------- 3. persist PATH --
  PROFILE_LINE=". \"$HOME/.nix-profile/etc/profile.d/nix.sh\""
  if [ -e "$HOME/.nix-profile/etc/profile.d/nix.sh" ]; then
    if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
      echo "$PROFILE_LINE" >> "$CLAUDE_ENV_FILE"
    else
      grep -qsF "$PROFILE_LINE" "$HOME/.bashrc" 2>/dev/null || echo "$PROFILE_LINE" >> "$HOME/.bashrc"
    fi
  fi

  # ------------------------------------------------------- 4. pre-warm --
  cd "${CLAUDE_PROJECT_DIR:-$PWD}" || true
  if [ -f flake.nix ]; then
    # Realise the dev shell with a persistent gc-root, referencing the
    # flake as `path:` — web checkouts are SHALLOW clones, and Nix's git
    # fetcher fails walking parent commits on them ("object not found");
    # `path:` hashes the working tree directly.  The --profile doubles as
    # a gc-root outside the working tree, so the realised paths survive
    # until the session and `git status` stays clean.  (Both mechanics
    # from fls PR #1255.)
    GCROOT="${FLS_DEVSHELL_GCROOT:-$HOME/.cache/fls/devshell-profile}"
    mkdir -p "$(dirname "$GCROOT")"
    log "realising 'nix develop' shell (gc-root: $GCROOT; a cold cache can take a while)..."
    if nix develop --profile "$GCROOT" "path:$PWD" --command true 2>&1 | sed 's/^/[nix-develop] /'; then
      log "toolchain realised; verifying agda:"
      nix develop --profile "$GCROOT" "path:$PWD" --command agda --version 2>&1 | sed 's/^/[agda] /' \
        || log "WARNING: agda not runnable from the realised shell. Non-fatal."
    else
      log "WARNING: 'nix develop' did not complete. If fetching flake inputs returned 403:"
      log "         the github: flake-ref shorthand is blocked by the sandbox's GitHub proxy —"
      log "         the git+https flake inputs from fls PR #1255 must be merged first. Non-fatal."
    fi
  else
    log "no flake.nix in ${PWD} — skipping pre-warm (is this the fls checkout?)"
  fi
else
  log "nix unavailable; toolchain steps skipped."
fi

# ------------------------------------------ 5. authorship + attribution --
# The authorship standing order (claude-tooling global/CLAUDE.md): commits
# from this container are authored by William, with no AI author/co-author
# metadata. Aligns the container's git identity and Claude Code's
# attribution settings; runs even in toolchain-only setups.
git config --global user.name "William DeMeo" 2>/dev/null || true
git config --global user.email "williamdemeo@gmail.com" 2>/dev/null || true
python3 - <<'PY' 2>/dev/null && log "git identity + attribution settings configured" \
  || log "WARNING: could not write attribution settings (python3 missing?). Non-fatal."
import json, os
path = os.path.expanduser("~/.claude/settings.json")
os.makedirs(os.path.dirname(path), exist_ok=True)
try:
    with open(path) as f:
        cfg = json.load(f)
except (FileNotFoundError, ValueError):
    cfg = {}
cfg["attribution"] = {"commit": "", "pr": "", "sessionUrl": False}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
PY

# ----------------------------------- 6. optional: William's Claude config --
# Installs into the container's ~/.claude ONLY — never into the repo working
# tree, so nothing can end up in a commit or PR.
if [ -n "${CLAUDE_TOOLING_TOKEN:-}" ]; then
  log "fetching williamdemeo/claude-tooling for skills + CLAUDE.md..."
  CT_DIR="$(mktemp -d)"
  if git clone --depth 1 \
       "https://x-access-token:${CLAUDE_TOOLING_TOKEN}@github.com/williamdemeo/claude-tooling.git" \
       "$CT_DIR" 2>&1 | sed 's/^/[clone] /'; then
    mkdir -p "$HOME/.claude/skills"
    for skill in "$CT_DIR"/global/skills/*/ "$CT_DIR"/projects/fls/claude/skills/*/; do
      [ -d "$skill" ] || continue
      cp -r "$skill" "$HOME/.claude/skills/$(basename "$skill")" 2>/dev/null || true
      log "skill installed: $(basename "$skill")"
    done
    # Global + fls CLAUDE.md content goes into the container-global file
    # (always loaded); guard on the fls probe marker for idempotency.
    if ! grep -qsF 'PROBE-MARKER: claude-tooling/fls' "$HOME/.claude/CLAUDE.md" 2>/dev/null; then
      { cat "$CT_DIR/global/CLAUDE.md"; echo; cat "$CT_DIR/projects/fls/CLAUDE.md"; } \
        >> "$HOME/.claude/CLAUDE.md"
      log "CLAUDE.md (global + fls) appended to ~/.claude/CLAUDE.md"
    else
      log "CLAUDE.md already installed (marker present)."
    fi
    rm -rf "$CT_DIR"
  else
    log "WARNING: could not clone claude-tooling (token scope? network policy?). Skipping config install."
  fi
else
  log "CLAUDE_TOOLING_TOKEN not set — skipping skills/CLAUDE.md install (toolchain-only setup)."
fi

log "done."
exit 0
