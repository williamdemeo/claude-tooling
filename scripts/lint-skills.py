#!/usr/bin/env python3
"""lint-skills.py — static checks over the skills and CLAUDE.md files in this
repo.  Python 3 stdlib only (the repo's one permitted non-bash dependency).

Checks (E = error → exit 1, W = warning):
  E frontmatter parses, has non-empty `name:` and `description:`
  E `name:` matches the skill's directory name
  W description shorter than 40 chars, or lacking a when-to-trigger cue
  E duplicate skill names within any set one session would see
    (global + ONE project; the same name in two different projects is fine)
  E absolute paths mentioned in skill bodies that no longer exist on disk
    (stale-path lint; lines containing 'lint-skills: ok' are exempt)
  E session-specific junk in skill bodies: long hex strings that look like
    commit SHAs, PR/issue number references (same exemption)
  W managed CLAUDE.md missing its visible PROBE-MARKER line

Usage: lint-skills.py [repo-root]
"""

import os
import re
import sys
from pathlib import Path

GREEN, RED, YELLOW, OFF = ("\033[32m", "\033[31m", "\033[33m", "\033[0m") \
    if sys.stdout.isatty() and not os.environ.get("NO_COLOR") else ("", "", "", "")

errors = 0
warnings = 0


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{OFF} {msg}")


def warn(msg: str) -> None:
    global warnings
    warnings += 1
    print(f"  {YELLOW}!{OFF} {msg}")


def err(msg: str) -> None:
    global errors
    errors += 1
    print(f"  {RED}✗{OFF} {msg}")


def parse_frontmatter(text: str):
    """Return (dict, body) for a leading '---' YAML-ish block of simple
    `key: value` lines (no yaml module in stdlib; skills use only that)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    fm = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fm, "\n".join(lines[i + 1:])
        m = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
        elif line.strip() and not line.startswith((" ", "\t")):
            return None, text  # malformed top-level line
    return None, text  # unterminated


TRIGGER_CUES = re.compile(r"\b(use (this|when|whenever|after|before|it)|when |whenever |trigger|invoke)", re.I)
PATH_RE = re.compile(r"(?:~|/home/williamdemeo)/[A-Za-z0-9._/@+-]+")
SHA_RE = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
PRNUM_RE = re.compile(r"\b(?:PR|pull request|issue)\s*#\d+|\bpull/\d+\b", re.I)
EXEMPT = "lint-skills: ok"


def lint_body(rel: str, body: str) -> None:
    for lineno, line in enumerate(body.splitlines(), start=1):
        if EXEMPT in line:
            continue
        for m in PATH_RE.finditer(line):
            p = m.group(0).rstrip(".,;:)]}\"'`")
            if any(c in p for c in "<>*$…"):
                continue
            expanded = Path(os.path.expanduser(p))
            if not expanded.exists():
                err(f"{rel}:{lineno} stale path: {p}")
        if SHA_RE.search(line):
            err(f"{rel}:{lineno} looks like a bare commit SHA (session junk): {line.strip()[:70]}")
        if PRNUM_RE.search(line):
            err(f"{rel}:{lineno} PR/issue number reference (session junk): {line.strip()[:70]}")


def lint_skill(root: Path, skill_dir: Path) -> str | None:
    """Lint one skill dir; return the skill name (or None)."""
    rel = skill_dir.relative_to(root).as_posix()
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        err(f"{rel}: no SKILL.md")
        return None
    fm, body = parse_frontmatter(md.read_text(encoding="utf-8"))
    if fm is None:
        err(f"{rel}: frontmatter missing or malformed")
        return None
    name = fm.get("name", "")
    desc = fm.get("description", "")
    if not name:
        err(f"{rel}: empty `name:`")
    elif name != skill_dir.name:
        err(f"{rel}: `name: {name}` does not match directory name")
    if not desc:
        err(f"{rel}: empty `description:`")
    else:
        if len(desc) < 40:
            warn(f"{rel}: description is short ({len(desc)} chars) — say when to trigger")
        elif not TRIGGER_CUES.search(desc):
            warn(f"{rel}: description has no when-to-trigger cue (use/when/after/…)")
    lint_body(f"{rel}/SKILL.md", body)
    return name or None


def skill_names(root: Path, skills_dir: Path) -> list[str]:
    names = []
    if skills_dir.is_dir():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir():
                n = lint_skill(root, d)
                if n:
                    names.append(n)
    return names


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent

    print(":: lint: global skills")
    global_names = skill_names(root, root / "global" / "skills")
    ok(f"global: {len(global_names)} skill(s): {', '.join(global_names) or '(none)'}")

    projects_dir = root / "projects"
    per_project: dict[str, list[str]] = {}
    for proj in sorted(p for p in projects_dir.iterdir() if p.is_dir()) if projects_dir.is_dir() else []:
        print(f":: lint: {proj.name}")
        names = skill_names(root, proj / "claude" / "skills")
        per_project[proj.name] = names
        ok(f"{proj.name}: {len(names)} skill(s): {', '.join(names) or '(none)'}")
        cm = proj / "CLAUDE.md"
        if not cm.is_file():
            err(f"projects/{proj.name}: no CLAUDE.md")
        elif not re.search(r"^PROBE-MARKER: ", cm.read_text(encoding="utf-8"), re.M):
            warn(f"projects/{proj.name}/CLAUDE.md: no visible PROBE-MARKER line (make probe will skip its CLAUDE.md check)")

    gcm = root / "global" / "CLAUDE.md"
    if not gcm.is_file():
        err("global/CLAUDE.md missing")
    elif not re.search(r"^PROBE-MARKER: ", gcm.read_text(encoding="utf-8"), re.M):
        warn("global/CLAUDE.md: no visible PROBE-MARKER line")

    print(":: lint: duplicate names within any one session's visible set")
    dup_found = False
    for proj, names in per_project.items():
        dups = sorted(set(global_names) & set(names)) + sorted(n for n in set(names) if names.count(n) > 1)
        for d in dups:
            err(f"duplicate skill name '{d}' visible in a {proj} session (global + {proj})")
            dup_found = True
    if len(global_names) != len(set(global_names)):
        err("duplicate names within global skills")
        dup_found = True
    if not dup_found:
        ok("no duplicates in any visible set")

    print(f":: lint summary: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
