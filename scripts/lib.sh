# scripts/lib.sh — shared logging, manifest parsing, and symlink primitives
# for the claude-tooling scripts.  Bash + POSIX awk + coreutils only.
#
# Every mutating primitive honors two globals (set by the calling script):
#   DRY_RUN=1  — print what would happen, touch nothing
#   FORCE=1    — allowed to replace real (non-symlink) files, with a backup
#
# Backups of anything replaced under --force go to
#   ~/.local/state/claude-tooling/backups/<timestamp>/<mirrored-absolute-path>
# so no stray *.bak files pollute checkouts.

# ---------------------------------------------------------------- logging --
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  _c_grn=$'\033[32m'; _c_red=$'\033[31m'; _c_ylw=$'\033[33m'; _c_blu=$'\033[34m'; _c_off=$'\033[0m'
else
  _c_grn=''; _c_red=''; _c_ylw=''; _c_blu=''; _c_off=''
fi

N_OK=0; N_WARN=0; N_ERR=0; N_PLAN=0; N_ATTN=0
ATTN_LINES=()

# Output markers:
#   ✓  done / already correct
#   →  planned action (dry-run only; the expected bulk of a dry-run)
#   !  expected or transitional state (e.g. tracked .claude skipped)
#   !! NEEDS ATTENTION — investigate before proceeding; recapped by summary()
#   ✗  hard error (nonzero exit)
say()  { printf '%s::%s %s\n' "$_c_blu" "$_c_off" "$*"; }
ok()   { printf '  %s✓%s %s\n' "$_c_grn" "$_c_off" "$*"; N_OK=$((N_OK+1)); }
plan() { printf '  %s→%s %s\n' "$_c_blu" "$_c_off" "$*"; N_PLAN=$((N_PLAN+1)); }
warn() { printf '  %s!%s %s\n' "$_c_ylw" "$_c_off" "$*"; N_WARN=$((N_WARN+1)); }
attn() { printf '  %s!!%s %s\n' "$_c_red" "$_c_off" "$*"; N_ATTN=$((N_ATTN+1)); ATTN_LINES+=("$*"); }
fail() { printf '  %s✗%s %s\n' "$_c_red" "$_c_off" "$*"; N_ERR=$((N_ERR+1)); }
die()  { fail "$*"; exit 1; }

summary() { # summary <label>  — recaps !! items, prints counts; returns 1 if any ✗
  local l counts
  if [ "$N_ATTN" -gt 0 ]; then
    printf '\n'
    say "${_c_red}NEEDS ATTENTION${_c_off} ($N_ATTN) — investigate before proceeding:"
    for l in "${ATTN_LINES[@]}"; do
      printf '  %s!!%s %s\n' "$_c_red" "$_c_off" "$l"
    done
  fi
  counts="$N_OK ok"
  [ "$N_PLAN" -gt 0 ] && counts="$counts, $N_PLAN planned"
  counts="$counts, $N_WARN warnings"
  [ "$N_ATTN" -gt 0 ] && counts="$counts, $N_ATTN NEED ATTENTION"
  counts="$counts, $N_ERR errors"
  say "$1: $counts"
  [ "$N_ERR" -eq 0 ]
}

# ------------------------------------------------------------- repo paths --
repo_root() { # absolute path of this repo's working tree
  ( cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd )
}

expand_tilde() { case "$1" in "~") printf '%s' "$HOME";; "~/"*) printf '%s%s' "$HOME" "${1#\~}";; *) printf '%s' "$1";; esac; }

# --------------------------------------------------------------- manifest --
# projects.toml is a deliberately restricted TOML subset so plain awk can
# parse it during catastrophe recovery: [section] headers (dots and quoted
# names allowed), `key = "string"`, `key = ["a", "b"]`.  No '#' inside
# values; inline comments after values are allowed.

manifest_rows() { # manifest_rows <file>  →  "section<TAB>key<TAB>value" lines
  awk '
    function trim(s){ sub(/^[ \t]+/,"",s); sub(/[ \t]+$/,"",s); return s }
    function unquote(s){ s=trim(s); if (s ~ /^".*"$/) s=substr(s,2,length(s)-2); return s }
    /^[ \t]*#/ { next }
    /^[ \t]*$/ { next }
    /^[ \t]*\[/ {
      line=trim($0); gsub(/^\[/,"",line); gsub(/\]$/,"",line); gsub(/"/,"",line)
      section=line; next
    }
    index($0,"=") > 0 {
      eq=index($0,"="); key=trim(substr($0,1,eq-1)); val=trim(substr($0,eq+1))
      sub(/[ \t]+#.*$/,"",val)
      if (val ~ /^\[.*\]$/) {
        gsub(/^\[/,"",val); gsub(/\]$/,"",val)
        n=split(val,parts,","); out=""
        for(i=1;i<=n;i++){ p=unquote(parts[i]); if(p!="") out=(out=="")?p:out" "p }
        val=out
      } else val=unquote(val)
      printf "%s\t%s\t%s\n", section, key, val
    }
  ' "$1"
}

manifest_projects() { # manifest_projects <file>  →  project names, one per line
  manifest_rows "$1" | awk -F'\t' '$1 ~ /^projects\./ { sub(/^projects\./,"",$1); print $1 }' | sort -u
}

manifest_get() { # manifest_get <file> <section> <key> [default]
  local v
  v="$(manifest_rows "$1" | awk -F'\t' -v s="$2" -v k="$3" '$1==s && $2==k {print $3; exit}')"
  printf '%s' "${v:-${4:-}}"
}

# --------------------------------------------------------------- backups --
BACKUP_STAMP="${BACKUP_STAMP:-$(date +%Y%m%d-%H%M%S)}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/.local/state/claude-tooling/backups}"

backup_move() { # backup_move <abs-path>  — move a real file/dir out of the way
  local src="$1" dest="$BACKUP_ROOT/$BACKUP_STAMP$1"
  mkdir -p "$(dirname "$dest")"
  mv "$src" "$dest"
  printf '%s' "$dest"
}

# ---------------------------------------------------------------- linking --
# ensure_link <target> <link> <desc>
#   Guarantee <link> is a symlink to <target>.
#   symlink→correct: ok.  symlink→wrong: re-point (loses nothing).
#   real file/dir: skip+warn, or backup+replace under FORCE.
#   absent: create.
ensure_link() {
  local target="$1" link="$2" desc="$3" cur dest
  if [ -L "$link" ]; then
    cur="$(readlink "$link")"
    if [ "$cur" = "$target" ]; then
      ok "$desc — already linked"
    elif [ "${DRY_RUN:-0}" = 1 ]; then
      plan "$desc — would re-point (now → $cur)"
    else
      rm "$link" && ln -s "$target" "$link"
      ok "$desc — re-pointed (was → $cur)"
    fi
  elif [ -e "$link" ]; then
    if [ "${FORCE:-0}" = 1 ]; then
      if [ "${DRY_RUN:-0}" = 1 ]; then
        plan "$desc — would replace real file/dir (backup, then link)"
      else
        dest="$(backup_move "$link")"
        ln -s "$target" "$link"
        ok "$desc — replaced real file/dir (backup: $dest)"
      fi
    else
      attn "$desc — real file/dir in the way; skipped (migrate it, or re-run with --force to backup+replace)"
    fi
  else
    if [ "${DRY_RUN:-0}" = 1 ]; then
      plan "$desc — would link → $target"
    else
      mkdir -p "$(dirname "$link")"
      ln -s "$target" "$link"
      ok "$desc — linked"
    fi
  fi
}

# ensure_realdir <dir> <desc>  — guarantee a real directory (not a symlink).
# A symlink pointing into this repo (older whole-dir scheme) is replaced by a
# real dir; any other symlink needs FORCE.
ensure_realdir() {
  local dir="$1" desc="$2" cur root
  root="$(repo_root)"
  if [ -L "$dir" ]; then
    cur="$(readlink "$dir")"
    case "$cur" in
      "$root"/*)
        if [ "${DRY_RUN:-0}" = 1 ]; then plan "$desc — would replace repo-pointing symlink with real dir"
        else rm "$dir" && mkdir -p "$dir"; ok "$desc — replaced repo-pointing symlink with real dir"; fi ;;
      *)
        if [ "${FORCE:-0}" = 1 ] && [ "${DRY_RUN:-0}" != 1 ]; then
          rm "$dir" && mkdir -p "$dir"; ok "$desc — replaced foreign symlink (→ $cur) with real dir"
        else
          attn "$desc — is a symlink (→ $cur); skipped (use --force)"
        fi ;;
    esac
  elif [ -d "$dir" ]; then
    ok "$desc — real dir present"
  elif [ -e "$dir" ]; then
    fail "$desc — exists but is not a directory"
  else
    if [ "${DRY_RUN:-0}" = 1 ]; then plan "$desc — would create dir"
    else mkdir -p "$dir"; ok "$desc — created"; fi
  fi
}

# ---------------------------------------------------------- git worktrees --
git_worktree_paths() { # git_worktree_paths <main-checkout>  → abs paths, main first
  git -C "$1" worktree list --porcelain 2>/dev/null | awk '/^worktree /{print substr($0,10)}'
}

git_common_dir() { # git_common_dir <checkout>  → absolute common .git dir
  ( cd "$1" && cd "$(git rev-parse --git-common-dir)" && pwd )
}

# ensure_exclude_line <main-checkout>  — /.claude in the shared info/exclude
ensure_exclude_line() {
  local main="$1" common file
  common="$(git_common_dir "$main")" || { fail "exclude — cannot resolve git common dir for $main"; return; }
  file="$common/info/exclude"
  if [ -f "$file" ] && grep -qxF '/.claude' "$file"; then
    ok "exclude — /.claude already in $file"
  elif [ "${DRY_RUN:-0}" = 1 ]; then
    plan "exclude — would append /.claude to $file"
  else
    mkdir -p "$common/info"
    printf '/.claude\n' >> "$file"
    ok "exclude — appended /.claude to $file"
  fi
}

# link_worktrees_for <parent> <main-checkout>
#   Give the main checkout and every linked worktree a root
#   .claude -> <parent>/.claude symlink; skip (and report) any checkout where
#   .claude is TRACKED content (transitional repos, pre-removal-PR).
link_worktrees_for() {
  local parent="$1" main="$2" wt base
  [ -d "$main" ] || { fail "worktrees — main checkout missing: $main"; return; }
  ensure_exclude_line "$main"
  while IFS= read -r wt; do
    [ -n "$wt" ] || continue
    base="${wt#"$parent"/}"
    if [ ! -d "$wt" ]; then
      warn "worktree $base — path missing on disk (stale entry; consider 'git worktree prune')"
      continue
    fi
    if [ -n "$(git -C "$wt" ls-files .claude 2>/dev/null)" ]; then
      warn "worktree $base — .claude is TRACKED content here; skipped (re-link after the removal PR lands and this checkout updates)"
      continue
    fi
    ensure_link "$parent/.claude" "$wt/.claude" "worktree $base/.claude"
  done < <(git_worktree_paths "$main")
}
