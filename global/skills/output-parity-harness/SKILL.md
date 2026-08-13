---
name: output-parity-harness
description: Prove a rewritten tool reproduces the old one's output byte-for-byte when the tool reads live, moving state (git worktrees, a home dir, a filesystem) — sandwich each new run between two old runs and only trust the diff when the two old runs agree. Use when porting or refactoring a script to another language, extracting a library, or any change with an "output must not change" contract; also use when a parity diff appears and you need to tell a real regression from drift underneath you.
---

# Byte-parity for a rewrite that reads live state

The trap: you capture a baseline, write the port, diff — and see a diff that
is not yours. The world moved between the two runs (a worktree was pruned, a
file appeared, a clock ticked). You then debug your port for an hour. Worse is
the silent case: drift *hides* a real diff by cancelling it out.

## The sandwich

Run **old → new → old again**. A verdict only counts when the two old runs are
identical; otherwise the state moved and the case is `SKIP`, not `PASS`.

```bash
run_case() {  # run_case <name> <old-cmd...> -- <new-cmd...>
  local name="$1"; shift
  local old=() ; while [ "$1" != "--" ]; do old+=("$1"); shift; done; shift
  "${old[@]}" > "$OUT/$name.old1" 2>&1; local rc1=$?
  "$@"        > "$OUT/$name.new"  2>&1; local rc2=$?
  "${old[@]}" > "$OUT/$name.old2" 2>&1

  diff -q "$OUT/$name.old1" "$OUT/$name.old2" >/dev/null \
    || { echo "SKIP $name — live state moved"; return; }
  [ "$rc1" = "$rc2" ] || echo "FAIL $name — exit $rc1 vs $rc2"
  diff "$OUT/$name.old1" "$OUT/$name.new" && echo "OK   $name"
}
```

Set `set -uo pipefail`, not `-e`: you want every case to run and report.

## Rules that make the diff meaningful

+ **Both implementations must coexist** in one checkout while you compare —
  do the entry-point swap in a *later* commit, so the harness is reproducible
  from that commit.
+ **Run both from the same directory.** Tools that derive their root from
  `$0`/`__file__` will otherwise print different absolute paths in every line.
+ **Redirect to files, never a tty**, so color codes are off on both sides and
  `2>&1` captures the same interleaving.
+ **Compare exit status too.** Same text, different status is a regression.
+ **Cover the documented invocations**, including the flag combinations the
  runbooks actually use, plus one positional-filter case and one no-args case.

## Re-running the harness after the old code is gone

You will want to re-verify parity after later review fixes, once the entry
points have already been swapped. Restore the old implementation from the
pre-swap commit, run, then put the new one back:

```bash
OLD=<pre-swap-sha>
FILES="install.sh scripts/lib.sh scripts/check.sh"      # every file you overwrite
for f in $FILES; do git show "$OLD:$f" > "$f"; done
./parity.sh
git checkout -- $FILES                                  # by NAME, never a directory
```

**Commit your new work before you do this**, and restore by explicit filename.
`git checkout -- scripts/` throws away every *uncommitted* change in that
directory — including the fixes you are trying to verify. Restoring a file
that the current commit deletes leaves it untracked, so `rm` those explicitly
afterwards and confirm with `git status`.

## Reading a diff that is genuinely yours

Match the old implementation's accidents before you decide it is a bug:

+ `awk substr()` is **bytes** under mawk, **characters** under gawk — a
  truncated column can differ by a multibyte character.
+ Shell globs and `sort` collate by `LC_COLLATE`; a rewrite that sorts by code
  point agrees for ASCII-ish names and diverges on punctuation and case.
+ Command substitution strips trailing newlines but keeps trailing **spaces**,
  so `$(printf '%s ' …)` lines end in an invisible space. Reproduce it — an
  empty diff is worth more than a tidier line.
+ Shell `[ -e ]` follows symlinks and `[ -L ]` does not; a dangling link is
  "exists" to one test and not the other.

## When "identical" is impossible

If the old and new outputs must differ for a defensible reason, say so in the
PR with the reason, and pin the intended behavior with a test instead of a
diff — do not quietly relax the harness to whitespace-insensitive.
