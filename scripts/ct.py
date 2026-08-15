#!/usr/bin/env python3
"""ct.py — the one command behind claude-tooling.

Deploys @williamdemeo's Claude Code configuration (this repo) into the live
locations as symlinks, and verifies the result — statically (`check`, `lint`,
`list`) or live, with real sessions (`probe`, `verify-discovery`).

Subcommands:

    install           deploy the global tier + every symlink-mode project
    link-worktrees    backfill root .claude links over a project's worktrees
    check             static verification: manifest, repo hygiene, link state
    list              inventory of managed CLAUDE.md files and skills by tier
    lint              repo hygiene alone (skills frontmatter, stale paths, …)
    probe             live `claude -p` verification matrix (costs tokens)
    verify-discovery  re-verify the discovery rules with throwaway fixtures
    add-project       scaffold a new symlink-mode project

Output markers:

    ✓  done / already correct          →   planned action (--dry-run only)
    !  expected or transitional        !!  NEEDS ATTENTION (recapped at end)
    ✗  hard error — the only thing that makes the exit status nonzero

Python >= 3.11 (for `tomllib`), stdlib only: this repo is what you reach for
during catastrophe recovery, so it must run before any toolchain exists.
"""

import sys

if sys.version_info < (3, 11):  # tomllib landed in 3.11; see docs/recovery.md
    raise SystemExit(
        f"ct.py needs Python >= 3.11 (stdlib tomllib); this is "
        f"{sys.version_info.major}.{sys.version_info.minor}"
    )

import argparse
import io
import os
import re
import shutil
import subprocess
import tempfile
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence, TextIO

MARKER_PREFIX = "PROBE-MARKER: claude-tooling/"
SKILLS_PROMPT = "Output only the names of your available skills, one per line. No other text."
MARKER_PROMPT = (
    "Output every line of your context that contains the string PROBE-MARKER, "
    "verbatim. If there are none, output exactly NONE."
)


class Fatal(Exception):
    """An unrecoverable error: reported as ✗ and exits 1 (the shell's `die`)."""


# --------------------------------------------------------------- reporting --


@dataclass(frozen=True)
class Palette:
    """ANSI colors — all empty when the stream is not a tty, or NO_COLOR is set."""

    grn: str = ""
    red: str = ""
    ylw: str = ""
    blu: str = ""
    off: str = ""

    @classmethod
    def for_stream(cls, stream: TextIO) -> "Palette":
        if stream.isatty() and not os.environ.get("NO_COLOR"):
            return cls("\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[0m")
        return cls()


class Reporter:
    """Streams the run's ✓ / → / ! / !! / ✗ lines and tallies them.

    The one piece of mutable state in this module; it is always passed
    explicitly rather than reached for as a global.  `!!` lines are also kept
    verbatim so `summary` can recap them — their absence at the end of a run
    is the user's green light.
    """

    def __init__(self, out: TextIO | None = None, palette: Palette | None = None) -> None:
        self.out: TextIO = out if out is not None else sys.stdout
        self.palette: Palette = palette if palette is not None else Palette.for_stream(self.out)
        self.n_ok = 0
        self.n_plan = 0
        self.n_warn = 0
        self.n_attn = 0
        self.n_err = 0
        self.attn_lines: list[str] = []

    def _emit(self, line: str) -> None:
        print(line, file=self.out)

    def say(self, msg: str) -> None:
        """Section header (`:: …`); not counted."""
        self._emit(f"{self.palette.blu}::{self.palette.off} {msg}")

    def ok(self, msg: str) -> None:
        self.n_ok += 1
        self._emit(f"  {self.palette.grn}✓{self.palette.off} {msg}")

    def plan(self, msg: str) -> None:
        """An action a --dry-run would have taken; counted separately."""
        self.n_plan += 1
        self._emit(f"  {self.palette.blu}→{self.palette.off} {msg}")

    def warn(self, msg: str) -> None:
        """Expected or transitional state — no action needed today."""
        self.n_warn += 1
        self._emit(f"  {self.palette.ylw}!{self.palette.off} {msg}")

    def attn(self, msg: str) -> None:
        """NEEDS ATTENTION: investigate before proceeding.  Recapped verbatim."""
        self.n_attn += 1
        self.attn_lines.append(msg)
        self._emit(f"  {self.palette.red}!!{self.palette.off} {msg}")

    def fail(self, msg: str) -> None:
        """Hard error: the run's exit status becomes 1."""
        self.n_err += 1
        self._emit(f"  {self.palette.red}✗{self.palette.off} {msg}")

    def summary(self, label: str) -> int:
        """Recap the `!!` lines, print the counts, return the exit status."""
        red, off = self.palette.red, self.palette.off
        if self.n_attn:
            self._emit("")
            self.say(
                f"{red}NEEDS ATTENTION{off} ({self.n_attn}) "
                f"— investigate before proceeding:"
            )
            for line in self.attn_lines:
                self._emit(f"  {red}!!{off} {line}")
        counts = f"{self.n_ok} ok"
        if self.n_plan:
            counts += f", {self.n_plan} planned"
        counts += f", {self.n_warn} warnings"
        if self.n_attn:
            counts += f", {self.n_attn} NEED ATTENTION"
        counts += f", {self.n_err} errors"
        self.say(f"{label}: {counts}")
        return 0 if self.n_err == 0 else 1


# ----------------------------------------------------------- paths & options --


def home() -> Path:
    """`$HOME` as the shell sees it (so fixtures can point it elsewhere)."""
    return Path(os.path.expanduser("~"))


def repo_root() -> Path:
    """This repo's working tree — this file lives in `<root>/scripts/`."""
    return Path(__file__).resolve().parent.parent


def expand_tilde(value: str) -> str:
    """Expand a leading `~` only (`~user` is left alone, as in the shell)."""
    if value == "~":
        return str(home())
    if value.startswith("~/"):
        return str(home()) + value[1:]
    return value


@dataclass(frozen=True)
class Options:
    """The two knobs every mutating primitive honors, plus where backups go."""

    dry_run: bool = False
    force: bool = False
    backup_root: Path = Path("/nonexistent")
    backup_stamp: str = "00000000-000000"

    @classmethod
    def from_env(cls, *, dry_run: bool = False, force: bool = False) -> "Options":
        """Build options, honoring BACKUP_ROOT / BACKUP_STAMP overrides."""
        return cls(
            dry_run=dry_run,
            force=force,
            backup_root=Path(
                os.environ.get("BACKUP_ROOT", str(home() / ".local/state/claude-tooling/backups"))
            ),
            backup_stamp=os.environ.get("BACKUP_STAMP", time.strftime("%Y%m%d-%H%M%S")),
        )


def selected(targets: Sequence[str], name: str) -> bool:
    """No positional targets selects everything; otherwise exact-name match."""
    return not targets or name in targets


def validate_targets(targets: Sequence[str], known: Iterable[str]) -> None:
    """Reject a target that names nothing, so a typo cannot look like success.

    Without this, `check flss` filters everything out and reports green
    without having checked the thing you asked about.
    """
    names = sorted(set(known))
    unknown = [t for t in targets if t not in names]
    if unknown:
        raise Fatal(f"unknown target(s): {' '.join(unknown)} — known: {' '.join(names)}")


# ------------------------------------------------------------------ manifest --


@dataclass(frozen=True)
class Project:
    """One `[projects.<name>]` stanza of projects.toml."""

    name: str
    parent_raw: str  # as written in the manifest, e.g. "~/git/IO/fls"
    parent: Path  # tilde-expanded
    main: str  # main-checkout dir name under parent
    mode: str  # "symlink" (managed here) | "committed" (never touched)

    @property
    def main_checkout(self) -> Path:
        return self.parent / self.main

    @property
    def is_symlink_mode(self) -> bool:
        return self.mode == "symlink"

    @property
    def parent_declared(self) -> bool:
        """Does the stanza name an absolute parent directory?

        A guard, not pedantry: `Path("")` is `.`, so a stanza with no
        `parent` would otherwise deploy into whatever directory the command
        happened to run from, and a relative one cannot produce the absolute
        symlink targets this design requires.  Callers must refuse to act on
        a project where this is false.
        """
        return bool(self.parent_raw) and self.parent.is_absolute()


@dataclass(frozen=True)
class Manifest:
    """projects.toml: `[meta]` plus the projects, ordered by name."""

    path: Path
    canonical_root: str  # raw `[meta] canonical_root`, "" if unset
    projects: tuple[Project, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(p.name for p in self.projects)

    def get(self, name: str) -> Project | None:
        return next((p for p in self.projects if p.name == name), None)


def _table(value: object, where: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Fatal(f"{where}: expected a table")
    return value


def _string(table: dict[str, object], key: str, default: str, where: str) -> str:
    value = table.get(key, default)
    if not isinstance(value, str):
        raise Fatal(f"{where}: `{key}` must be a string")
    return value


def load_manifest(path: Path) -> Manifest:
    """Parse projects.toml (real TOML — `tomllib`, no subset restrictions)."""
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError:
        raise Fatal(f"manifest missing: {path}") from None
    except tomllib.TOMLDecodeError as exc:
        raise Fatal(f"{path}: invalid TOML — {exc}") from None

    meta = _table(data.get("meta", {}), f"{path}: [meta]")
    stanzas = _table(data.get("projects", {}), f"{path}: [projects]")
    projects = tuple(
        Project(
            name=name,
            parent_raw=_string(_table(body, f"{path}: [projects.{name}]"), "parent", "", name),
            parent=Path(
                expand_tilde(
                    _string(_table(body, f"{path}: [projects.{name}]"), "parent", "", name)
                )
            ),
            main=_string(_table(body, f"{path}: [projects.{name}]"), "main", "main", name),
            mode=_string(_table(body, f"{path}: [projects.{name}]"), "mode", "symlink", name),
        )
        for name, body in sorted(stanzas.items())
    )
    return Manifest(
        path=path,
        canonical_root=_string(meta, "canonical_root", "", f"{path}: [meta]"),
        projects=projects,
    )


# -------------------------------------------------------- filesystem helpers --


def subdirs(directory: Path) -> list[Path]:
    """Directories inside `directory`, by name — the shell's `<dir>/*/` glob.

    Symlinks to directories count; dotfiles do not.
    """
    if not directory.is_dir():
        return []
    return [p for p in sorted(directory.iterdir()) if not p.name.startswith(".") and p.is_dir()]


def members(directory: Path) -> list[Path]:
    """Existing entries of `directory`, by name — the shell's `<dir>/*` glob.

    Dangling symlinks are skipped, matching the shell's `[ -e "$member" ]`.
    """
    if not directory.is_dir():
        return []
    return [p for p in sorted(directory.iterdir()) if not p.name.startswith(".") and p.exists()]


def glob_entries(directory: Path) -> list[Path]:
    """Entries of `directory` in `<dir>/*` then `<dir>/.[!.]*` order.

    That is: visible names first, then dotted ones (`..foo` excluded, exactly
    as the shell glob excludes it).  Used by the orphan sweeps, which must see
    dotfiles.
    """
    if not directory.is_dir():
        return []
    names = sorted(p.name for p in directory.iterdir())
    visible = [n for n in names if not n.startswith(".")]
    dotted = [n for n in names if n.startswith(".") and not n.startswith("..")]
    return [directory / n for n in visible + dotted]


def points_into(target: str, root: Path) -> bool:
    """Is this raw symlink target a path inside `root`?"""
    return target.startswith(f"{root}/")


def line_count(path: Path) -> int:
    """Newlines in a file — `wc -l`."""
    return path.read_bytes().count(b"\n")


def truncate_bytes(text: str, limit: int) -> str:
    """First `limit` bytes of `text`, never splitting a character.

    The shell used `awk substr($0,1,100)`, which is byte-based under mawk;
    keeping bytes keeps the inventory columns aligned for ASCII descriptions,
    and dropping a partial character keeps the output valid UTF-8.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= limit:
        return text
    return encoded[:limit].decode("utf-8", errors="ignore")


# ---------------------------------------------------------- link primitives --


def backup_move(source: Path, opts: Options) -> Path:
    """Move a real file/dir into the timestamped central backup tree.

    `~/.local/state/claude-tooling/backups/<stamp><absolute-path>`, mirroring
    the original path — never a `*.bak` sibling that would show up as an
    untracked file in some checkout.
    """
    dest = opts.backup_root / f"{opts.backup_stamp}{source}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(dest))
    return dest


@dataclass(frozen=True)
class LinkPlan:
    """What `ensure_link` decided about one link, before touching anything."""

    action: str  # "ok" | "repoint" | "replace" | "blocked" | "create"
    current: str = ""  # existing symlink target, for "ok"/"repoint"


def plan_link(target: str, link: Path, *, force: bool) -> LinkPlan:
    """Classify a link site.  Pure: no filesystem writes, no printing.

    A symlink is judged by STRING equality of its raw target (both sides are
    absolute), so a correct-looking link into a different checkout is a
    re-point, not a no-op.
    """
    if link.is_symlink():
        current = os.readlink(link)
        return LinkPlan("ok" if current == target else "repoint", current)
    if link.exists():
        return LinkPlan("replace" if force else "blocked")
    return LinkPlan("create")


def ensure_link(target: str, link: Path, desc: str, rep: Reporter, opts: Options) -> None:
    """Guarantee `link` is a symlink to `target`, reporting what happened.

    Correct symlink → ✓; wrong symlink → silently re-pointed (the old target
    is logged); real file/dir → `!!` skip unless --force, which backs the
    original up first; absent → created, parents included.
    """
    plan = plan_link(target, link, force=opts.force)
    if plan.action == "ok":
        rep.ok(f"{desc} — already linked")
    elif plan.action == "repoint":
        if opts.dry_run:
            rep.plan(f"{desc} — would re-point (now → {plan.current})")
        else:
            link.unlink()
            link.symlink_to(target)
            rep.ok(f"{desc} — re-pointed (was → {plan.current})")
    elif plan.action == "replace":
        if opts.dry_run:
            rep.plan(f"{desc} — would replace real file/dir (backup, then link)")
        else:
            dest = backup_move(link, opts)
            link.symlink_to(target)
            rep.ok(f"{desc} — replaced real file/dir (backup: {dest})")
    elif plan.action == "blocked":
        rep.attn(
            f"{desc} — real file/dir in the way; skipped "
            f"(migrate it, or re-run with --force to backup+replace)"
        )
    else:  # "create"
        if opts.dry_run:
            rep.plan(f"{desc} — would link → {target}")
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target)
            rep.ok(f"{desc} — linked")


@dataclass(frozen=True)
class DirPlan:
    """What `ensure_realdir` decided about one directory site."""

    action: str  # "ok" | "repo_link" | "foreign_link" | "not_a_dir" | "create"
    current: str = ""  # existing symlink target, for the two link cases


def plan_realdir(directory: Path, root: Path) -> DirPlan:
    """Classify a site that must hold a REAL directory.  Pure.

    A symlink into this repo is the legacy whole-directory scheme and is
    replaced outright; any other symlink is somebody else's and needs --force.
    """
    if directory.is_symlink():
        current = os.readlink(directory)
        return DirPlan("repo_link" if points_into(current, root) else "foreign_link", current)
    if directory.is_dir():
        return DirPlan("ok")
    if directory.exists():
        return DirPlan("not_a_dir")
    return DirPlan("create")


def ensure_realdir(directory: Path, desc: str, root: Path, rep: Reporter, opts: Options) -> bool:
    """Guarantee `directory` is a real directory, not a symlink.

    The parent `.claude` dirs must stay real so machine-local state Claude
    Code writes there (settings.local.json, …) never lands in this repo.

    Returns whether a real directory is (or, under --dry-run, would be) in
    place.  Callers MUST honor a false: linking into a foreign symlink we
    just declined to touch would write into somebody else's directory, and
    linking under a plain file raises.
    """
    plan = plan_realdir(directory, root)
    if plan.action == "repo_link":
        if opts.dry_run:
            rep.plan(f"{desc} — would replace repo-pointing symlink with real dir")
        else:
            directory.unlink()
            directory.mkdir(parents=True, exist_ok=True)
            rep.ok(f"{desc} — replaced repo-pointing symlink with real dir")
        return True
    if plan.action == "foreign_link":
        if opts.force and not opts.dry_run:
            directory.unlink()
            directory.mkdir(parents=True, exist_ok=True)
            rep.ok(f"{desc} — replaced foreign symlink (→ {plan.current}) with real dir")
        else:
            rep.attn(f"{desc} — is a symlink (→ {plan.current}); skipped (use --force)")
        # A --force run establishes the dir, so a --dry-run --force still
        # predicts the child links; without --force nothing below may run.
        return opts.force
    if plan.action == "ok":
        rep.ok(f"{desc} — real dir present")
        return True
    if plan.action == "not_a_dir":
        rep.fail(f"{desc} — exists but is not a directory")
        return False
    if opts.dry_run:  # "create"
        rep.plan(f"{desc} — would create dir")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        rep.ok(f"{desc} — created")
    return True


# ----------------------------------------------------------------------- git --


def git(args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run git in `cwd`, capturing output; never raises on a nonzero status."""
    try:
        return subprocess.run(
            ["git", "-C", str(cwd), *args], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        raise Fatal("git is not on PATH") from None


def worktree_paths(main_checkout: Path) -> list[Path]:
    """Every checkout git knows about, main first.

    `git worktree list --porcelain` is the ONLY source of truth here: the
    manifest deliberately records no worktree list, because worktrees live
    under a dozen different container dirs and a list would be a lie waiting
    to happen.
    """
    proc = git(["worktree", "list", "--porcelain"], main_checkout)
    if proc.returncode != 0:
        return []
    prefix = "worktree "
    return [Path(ln[len(prefix) :]) for ln in proc.stdout.splitlines() if ln.startswith(prefix)]


def git_common_dir(checkout: Path) -> Path | None:
    """The shared `.git` directory, absolute — None if this is not a checkout."""
    proc = git(["rev-parse", "--git-common-dir"], checkout)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return (checkout / proc.stdout.strip()).resolve()


def claude_is_tracked(checkout: Path) -> bool:
    """Is `.claude` TRACKED content here?  Such checkouts are never touched.

    Replacing tracked content would dirty the checkout, so this wins even over
    --force; the transitional repos stay skipped until their removal PR lands.
    """
    return bool(git(["ls-files", ".claude"], checkout).stdout.strip())


def is_git_checkout(path: Path) -> bool:
    return git(["rev-parse", "--git-dir"], path).returncode == 0


def tracked_files(root: Path) -> list[str]:
    return git(["ls-files"], root).stdout.splitlines()


# ------------------------------------------------------- worktree deployment --


def ensure_exclude_line(main_checkout: Path, rep: Reporter, opts: Options) -> None:
    """Idempotently add `/.claude` to the shared `.git/info/exclude`.

    One exclude file is shared by every linked worktree, and exclude only
    affects untracked files — so this is safe even while a repo still tracks
    `.claude`.
    """
    common = git_common_dir(main_checkout)
    if common is None:
        rep.fail(f"exclude — cannot resolve git common dir for {main_checkout}")
        return
    path = common / "info" / "exclude"
    if path.is_file() and "/.claude" in path.read_text(encoding="utf-8").splitlines():
        rep.ok(f"exclude — /.claude already in {path}")
    elif opts.dry_run:
        rep.plan(f"exclude — would append /.claude to {path}")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write("/.claude\n")
        rep.ok(f"exclude — appended /.claude to {path}")


def relative_label(path: Path, parent: Path) -> str:
    """`<parent>/x/y` → `x/y`; anything outside `parent` keeps its full path."""
    text = str(path)
    prefix = f"{parent}/"
    return text[len(prefix) :] if text.startswith(prefix) else text


def link_worktrees_for(project: Project, rep: Reporter, opts: Options) -> None:
    """Give the main checkout and every linked worktree its root `.claude` link.

    Skills are discovered only from `.claude/skills/` at the session's worktree
    root, which is why every worktree needs its own link.
    """
    main = project.main_checkout
    if not main.is_dir():
        rep.fail(f"worktrees — main checkout missing: {main}")
        return
    ensure_exclude_line(main, rep, opts)
    for worktree in worktree_paths(main):
        label = relative_label(worktree, project.parent)
        if not worktree.is_dir():
            rep.warn(
                f"worktree {label} — path missing on disk "
                f"(stale entry; consider 'git worktree prune')"
            )
        elif claude_is_tracked(worktree):
            rep.warn(
                f"worktree {label} — .claude is TRACKED content here; skipped "
                f"(re-link after the removal PR lands and this checkout updates)"
            )
        else:
            ensure_link(
                f"{project.parent}/.claude",
                worktree / ".claude",
                f"worktree {label}/.claude",
                rep,
                opts,
            )


# ------------------------------------------------------------------ install --


def install_global(root: Path, rep: Reporter, opts: Options) -> None:
    """Deploy the global tier: `~/.claude/CLAUDE.md` + per-skill links."""
    live = home() / ".claude"
    rep.say("global → ~/.claude")
    ensure_link(f"{root}/global/CLAUDE.md", live / "CLAUDE.md", "~/.claude/CLAUDE.md", rep, opts)
    if not ensure_realdir(live / "skills", "~/.claude/skills", root, rep, opts):
        return
    for skill in subdirs(root / "global" / "skills"):
        ensure_link(
            str(skill), live / "skills" / skill.name, f"~/.claude/skills/{skill.name}", rep, opts
        )


def install_project(project: Project, root: Path, rep: Reporter, opts: Options) -> None:
    """Deploy one project: parent CLAUDE.md, `.claude` members, worktree links."""
    rep.say(f"project {project.name} → {project.parent}  (mode: {project.mode})")
    if project.mode == "committed":
        rep.ok("committed-mode project — config lives in its own repo; nothing to do")
        return

    repo_dir = root / "projects" / project.name
    if not project.parent_declared:
        rep.fail(f"parent dir missing: {project.parent_raw}")
        return
    if not project.parent.is_dir():
        rep.fail(f"parent dir missing: {project.parent}")
        return
    if not repo_dir.is_dir():
        rep.fail(f"repo dir missing: {repo_dir}")
        return

    ensure_link(
        f"{repo_dir}/CLAUDE.md",
        project.parent / "CLAUDE.md",
        f"{project.name}/CLAUDE.md",
        rep,
        opts,
    )
    if not ensure_realdir(project.parent / ".claude", f"{project.name}/.claude", root, rep, opts):
        return  # nothing below may write into (or through) that path

    for member in members(repo_dir / "claude"):
        if member.name == "skills":
            skills_dir_ok = ensure_realdir(
                project.parent / ".claude/skills", f"{project.name}/.claude/skills", root, rep, opts
            )
            for skill in subdirs(member) if skills_dir_ok else []:
                ensure_link(
                    str(skill),
                    project.parent / ".claude/skills" / skill.name,
                    f"{project.name}/.claude/skills/{skill.name}",
                    rep,
                    opts,
                )
        elif member.name == "settings.local.json":
            rep.warn(
                f"repo contains a settings.local.json for {project.name} — "
                f"that file is machine-local; not linking it"
            )
        else:
            ensure_link(
                str(member),
                project.parent / ".claude" / member.name,
                f"{project.name}/.claude/{member.name}",
                rep,
                opts,
            )

    if project.main_checkout.is_dir():
        link_worktrees_for(project, rep, opts)
    else:
        rep.fail(f"main checkout missing: {project.main_checkout}")


def warn_if_not_canonical(root: Path, manifest: Manifest, rep: Reporter) -> None:
    """Live config follows the canonical checkout; anywhere else links wrongly."""
    canonical = expand_tilde(manifest.canonical_root)
    if canonical and str(root) != canonical:
        rep.warn(
            f"running from {root}, not the canonical checkout ({canonical}) "
            f"— links will point HERE"
        )


def cmd_install(args: argparse.Namespace, rep: Reporter) -> int:
    """install — deploy every symlink into place; idempotent, backups on --force."""
    root = repo_root()
    manifest = load_manifest(root / "projects.toml")
    opts = Options.from_env(dry_run=args.dry_run, force=args.force)
    validate_targets(args.targets, ("global", *manifest.names))

    warn_if_not_canonical(root, manifest, rep)
    if opts.dry_run:
        rep.say("DRY RUN — nothing will be touched")

    if selected(args.targets, "global"):
        install_global(root, rep, opts)
    for project in manifest.projects:
        if selected(args.targets, project.name):
            install_project(project, root, rep, opts)
    return rep.summary("install")


def cmd_link_worktrees(args: argparse.Namespace, rep: Reporter) -> int:
    """link-worktrees — backfill root `.claude` links over a project's worktrees."""
    root = repo_root()
    manifest = load_manifest(root / "projects.toml")
    opts = Options.from_env(dry_run=args.dry_run, force=args.force)

    names = list(manifest.names) if args.all else list(args.targets)
    if not names:
        raise Fatal(f"no project given (or use --all); known: {' '.join(manifest.names)}")

    for name in names:
        project = manifest.get(name)
        if project is None:
            rep.fail(f"unknown project: {name}")
            continue
        rep.say(
            f"link worktrees: {name}  ({project.parent}, main checkout: {project.main})"
        )
        if project.mode == "committed":
            rep.ok(
                "committed-mode project — worktrees carry their own tracked .claude; "
                "nothing to do"
            )
        elif not project.parent_declared:
            rep.fail(f"no absolute parent in the manifest for {name}: {project.parent_raw}")
        elif not project.main_checkout.is_dir():
            rep.fail(f"main checkout missing: {project.main_checkout}")
        else:
            link_worktrees_for(project, rep, opts)
    return rep.summary("link-worktrees")


# --------------------------------------------------------------------- lint --

TRIGGER_CUES = re.compile(
    r"\b(use (this|when|whenever|after|before|it)|when |whenever |trigger|invoke)", re.I
)
PATH_RE = re.compile(r"(?:~|/home/williamdemeo)/[A-Za-z0-9._/@+-]+")
SHA_RE = re.compile(r"\b(?=[0-9a-f]*\d)(?=[0-9a-f]*[a-f])[0-9a-f]{7,40}\b")
PRNUM_RE = re.compile(r"\b(?:PR|pull request|issue)\s*#\d+|\bpull/\d+\b", re.I)
MARKER_RE = re.compile(r"^PROBE-MARKER: ", re.M)
EXEMPT = "lint-skills: ok"


def parse_frontmatter(text: str) -> tuple[dict[str, str], str] | tuple[None, str]:
    """Split a leading `---` block of simple `key: value` lines from the body.

    Skills use only that shape, and the stdlib has no YAML parser; anything
    fancier (or unterminated) is reported as malformed rather than guessed at.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, text
    fields: dict[str, str] = {}
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return fields, "\n".join(lines[index + 1 :])
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
        elif line.strip() and not line.startswith((" ", "\t")):
            return None, text  # malformed top-level line
    return None, text  # unterminated


def stale_paths(line: str) -> list[str]:
    """Absolute paths mentioned in a line that no longer exist on disk.

    Placeholders (`<>`, `*`, `$`, `…`) are not real paths, and trailing prose
    punctuation is not part of one.
    """
    found = []
    for match in PATH_RE.finditer(line):
        candidate = match.group(0).rstrip(".,;:)]}\"'`")
        if any(ch in candidate for ch in "<>*$…"):
            continue
        if not Path(os.path.expanduser(candidate)).exists():
            found.append(candidate)
    return found


def lint_body(rel: str, body: str, rep: Reporter) -> None:
    """Flag stale absolute paths and session-specific junk in a skill body."""
    for lineno, line in enumerate(body.splitlines(), start=1):
        if EXEMPT in line:
            continue
        for path in stale_paths(line):
            rep.fail(f"{rel}:{lineno} stale path: {path}")
        if SHA_RE.search(line):
            rep.fail(
                f"{rel}:{lineno} looks like a bare commit SHA (session junk): "
                f"{line.strip()[:70]}"
            )
        if PRNUM_RE.search(line):
            rep.fail(
                f"{rel}:{lineno} PR/issue number reference (session junk): {line.strip()[:70]}"
            )


def lint_skill(root: Path, skill_dir: Path, rep: Reporter) -> str | None:
    """Lint one skill directory; return its declared name, if it has a valid one."""
    rel = skill_dir.relative_to(root).as_posix()
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        rep.fail(f"{rel}: no SKILL.md")
        return None
    fields, body = parse_frontmatter(md.read_text(encoding="utf-8"))
    if fields is None:
        rep.fail(f"{rel}: frontmatter missing or malformed")
        return None
    name = fields.get("name", "")
    desc = fields.get("description", "")
    if not name:
        rep.fail(f"{rel}: empty `name:`")
    elif name != skill_dir.name:
        rep.fail(f"{rel}: `name: {name}` does not match directory name")
    if not desc:
        rep.fail(f"{rel}: empty `description:`")
    elif len(desc) < 40:
        rep.warn(f"{rel}: description is short ({len(desc)} chars) — say when to trigger")
    elif not TRIGGER_CUES.search(desc):
        rep.warn(f"{rel}: description has no when-to-trigger cue (use/when/after/…)")
    lint_body(f"{rel}/SKILL.md", body, rep)
    return name or None


def lint_skill_dir(root: Path, skills_dir: Path, rep: Reporter) -> list[str]:
    """Lint every skill under `skills_dir`, returning the names it declares."""
    return [
        name
        for name in (lint_skill(root, d, rep) for d in subdirs(skills_dir))
        if name is not None
    ]


def check_marker(path: Path, label: str, rep: Reporter, hint: str = "") -> None:
    """Warn unless this managed CLAUDE.md carries a VISIBLE marker line.

    Visible, because HTML comments are stripped from CLAUDE.md before
    injection — a commented-out marker is invisible to `probe`.
    """
    if not MARKER_RE.search(path.read_text(encoding="utf-8")):
        rep.warn(f"{label}: no visible PROBE-MARKER line{hint}")


def run_lint(root: Path, rep: Reporter) -> int:
    """The repo-hygiene pass: skills frontmatter, duplicates, stale paths, markers.

    Duplicates are judged per VISIBLE SET — global plus ONE project — because
    that is what a single session sees; the same skill name in two different
    projects is fine.
    """
    rep.say("lint: global skills")
    global_names = lint_skill_dir(root, root / "global" / "skills", rep)
    rep.ok(f"global: {len(global_names)} skill(s): {', '.join(global_names) or '(none)'}")

    per_project: dict[str, list[str]] = {}
    projects_dir = root / "projects"
    for project_dir in subdirs(projects_dir):
        rep.say(f"lint: {project_dir.name}")
        names = lint_skill_dir(root, project_dir / "claude" / "skills", rep)
        per_project[project_dir.name] = names
        rep.ok(f"{project_dir.name}: {len(names)} skill(s): {', '.join(names) or '(none)'}")
        claude_md = project_dir / "CLAUDE.md"
        if not claude_md.is_file():
            rep.fail(f"projects/{project_dir.name}: no CLAUDE.md")
        else:
            check_marker(
                claude_md,
                f"projects/{project_dir.name}/CLAUDE.md",
                rep,
                " (make probe will skip its CLAUDE.md check)",
            )

    global_md = root / "global" / "CLAUDE.md"
    if not global_md.is_file():
        rep.fail("global/CLAUDE.md missing")
    else:
        check_marker(global_md, "global/CLAUDE.md", rep)

    rep.say("lint: duplicate names within any one session's visible set")
    duplicates = False
    for project, names in per_project.items():
        clashes = sorted(set(global_names) & set(names))
        clashes += sorted(n for n in set(names) if names.count(n) > 1)
        for name in clashes:
            rep.fail(
                f"duplicate skill name '{name}' visible in a {project} session "
                f"(global + {project})"
            )
            duplicates = True
    if len(global_names) != len(set(global_names)):
        rep.fail("duplicate names within global skills")
        duplicates = True
    if not duplicates:
        rep.ok("no duplicates in any visible set")

    rep.say(f"lint summary: {rep.n_err} error(s), {rep.n_warn} warning(s)")
    return 0 if rep.n_err == 0 else 1


def cmd_lint(args: argparse.Namespace, rep: Reporter) -> int:
    """lint — repo hygiene over this repo's skills and managed CLAUDE.md files."""
    root = Path(args.root).resolve() if args.root else repo_root()
    return run_lint(root, rep)


# -------------------------------------------------------------------- check --


def classify_link(target: str, link: Path, root: Path, desc: str, rep: Reporter) -> None:
    """Report one expected live location's install state.

    ✓ linked; `!` pending (a real file, or nothing yet — the expected state
    before that migration stage); ✗ only for genuine breakage, so `check` stays
    green-with-warnings throughout the migration.
    """
    if link.is_symlink():
        current = os.readlink(link)
        if current == target:
            if link.exists():
                rep.ok(f"{desc} → linked")
            else:
                rep.fail(f"{desc} → correct symlink but target missing in repo: {target}")
        elif points_into(current, root):
            rep.fail(f"{desc} → symlink into repo but WRONG target (→ {current})")
        else:
            rep.fail(f"{desc} → symlink to foreign target (→ {current})")
    elif link.exists():
        rep.warn(f"{desc} → real file/dir (pending migration)")
    else:
        rep.warn(f"{desc} → absent (not installed yet)")


def sweep_orphans(directory: Path, desc: str, root: Path, rep: Reporter) -> None:
    """Flag depth-1 symlinks into this repo that dangle (e.g. a renamed skill)."""
    for entry in glob_entries(directory):
        if not entry.is_symlink():
            continue
        current = os.readlink(entry)
        if points_into(current, root) and not entry.exists():
            rep.fail(f"{desc}: orphaned repo link {entry.name} (→ {current})")


def check_manifest(manifest: Manifest, root: Path, rep: Reporter) -> None:
    """Layer 1: the manifest parses and every path it names exists."""
    if not manifest.projects:
        raise Fatal("no projects parsed from manifest")
    rep.ok("parsed projects: " + "".join(f"{name} " for name in manifest.names))

    for project in manifest.projects:
        if project.mode not in ("symlink", "committed"):
            rep.fail(f"{project.name}: invalid mode '{project.mode}'")
        if not project.parent_declared:
            rep.fail(f"{project.name}: parent missing: {project.parent_raw}")
            continue  # every path below would be relative to the cwd
        if not project.parent.is_dir():
            rep.fail(f"{project.name}: parent missing: {project.parent}")
        if not project.main_checkout.is_dir():
            rep.fail(f"{project.name}: main checkout missing: {project.main_checkout}")
        if project.is_symlink_mode and not (root / "projects" / project.name).is_dir():
            rep.fail(f"{project.name}: symlink-mode but no projects/{project.name} dir in repo")
        if project.main_checkout.is_dir() and not is_git_checkout(project.main_checkout):
            rep.warn(f"{project.name}: {project.main_checkout} is not a git checkout")


def check_hygiene(root: Path, rep: Reporter) -> None:
    """Layer 2: the lint, plus the machine-local-state-never-committed rule."""
    rep.say("repo hygiene")
    if run_lint(root, Reporter(rep.out, rep.palette)) == 0:  # its own tallies
        rep.ok("lint-skills passed")
    else:
        rep.fail("lint-skills reported errors")
    local_state = ("settings.local.json", "/settings.local.json")
    if any(f == local_state[0] or f.endswith(local_state[1]) for f in tracked_files(root)):
        rep.fail("settings.local.json is TRACKED in this repo — it is machine-local; untrack it")
    else:
        rep.ok("no settings.local.json tracked")


def check_global_state(root: Path, rep: Reporter) -> None:
    """Layer 3, global tier."""
    rep.say("install state: global → ~/.claude")
    classify_link(
        f"{root}/global/CLAUDE.md",
        home() / ".claude/CLAUDE.md",
        root,
        "~/.claude/CLAUDE.md",
        rep,
    )
    for skill in subdirs(root / "global" / "skills"):
        classify_link(
            str(skill),
            home() / ".claude/skills" / skill.name,
            root,
            f"~/.claude/skills/{skill.name}",
            rep,
        )
    sweep_orphans(home() / ".claude/skills", "~/.claude/skills", root, rep)


@dataclass
class WorktreeTally:
    """Per-project worktree census — the shape of a project's deployment."""

    linked: int = 0
    tracked: int = 0
    missing: int = 0
    absent: int = 0


def check_worktrees(project: Project, rep: Reporter) -> None:
    """Layer 3, worktrees: count states, and flag only genuinely bad links."""
    tally = WorktreeTally()
    expected = f"{project.parent}/.claude"
    for worktree in worktree_paths(project.main_checkout):
        link = worktree / ".claude"
        if not worktree.is_dir():
            tally.missing += 1
        elif claude_is_tracked(worktree):
            tally.tracked += 1
        elif not link.is_symlink():
            tally.absent += 1
        elif os.readlink(link) == expected and link.exists():
            tally.linked += 1
        else:
            rep.fail(
                f"{project.name} worktree {relative_label(worktree, project.parent)}: "
                f"bad .claude link (→ {os.readlink(link)})"
            )
    rep.ok(f"{project.name} worktrees: {tally.linked} linked")
    if tally.tracked:
        rep.warn(
            f"{project.name} worktrees: {tally.tracked} with tracked .claude "
            f"(transitional — re-link after removal PR)"
        )
    if tally.absent:
        rep.warn(
            f"{project.name} worktrees: {tally.absent} without .claude link "
            f"(run scripts/link-worktrees.sh {project.name})"
        )
    if tally.missing:
        rep.warn(
            f"{project.name} worktrees: {tally.missing} stale entries missing on disk "
            f"(git worktree prune)"
        )

    common = git_common_dir(project.main_checkout)
    exclude = (common / "info" / "exclude") if common else None
    listed = (
        exclude is not None
        and exclude.is_file()
        and "/.claude" in exclude.read_text(encoding="utf-8").splitlines()
    )
    if listed:
        rep.ok(f"{project.name}: /.claude present in shared info/exclude")
    else:
        rep.warn(
            f"{project.name}: /.claude not in {common if common else ''}/info/exclude "
            f"(install adds it)"
        )


def check_project_state(project: Project, root: Path, rep: Reporter) -> None:
    """Layer 3 for one project: parent CLAUDE.md, `.claude` members, worktrees."""
    rep.say(f"install state: {project.name} → {project.parent}")
    repo_dir = root / "projects" / project.name
    classify_link(
        f"{repo_dir}/CLAUDE.md",
        project.parent / "CLAUDE.md",
        root,
        f"{project.name}/CLAUDE.md",
        rep,
    )

    dot_claude = project.parent / ".claude"
    if dot_claude.is_symlink():
        rep.fail(
            f"{project.name}/.claude is a symlink — expected a real dir with per-member links"
        )
    elif dot_claude.is_dir():
        for member in members(repo_dir / "claude"):
            if member.name == "skills":
                for skill in subdirs(member):
                    classify_link(
                        str(skill),
                        dot_claude / "skills" / skill.name,
                        root,
                        f"{project.name}/.claude/skills/{skill.name}",
                        rep,
                    )
            else:
                classify_link(
                    str(member),
                    dot_claude / member.name,
                    root,
                    f"{project.name}/.claude/{member.name}",
                    rep,
                )
        sweep_orphans(dot_claude, f"{project.name}/.claude", root, rep)
        sweep_orphans(dot_claude / "skills", f"{project.name}/.claude/skills", root, rep)
    else:
        rep.warn(f"{project.name}/.claude — absent (not installed yet)")

    if project.main_checkout.is_dir():
        check_worktrees(project, rep)


def cmd_check(args: argparse.Namespace, rep: Reporter) -> int:
    """check — static verification of manifest, repo hygiene, and install state."""
    root = repo_root()
    manifest_path = root / "projects.toml"
    rep.say(f"manifest: {manifest_path}")
    if not manifest_path.is_file():
        raise Fatal("projects.toml missing")
    manifest = load_manifest(manifest_path)
    validate_targets(args.targets, ("global", *manifest.names))

    check_manifest(manifest, root, rep)
    check_hygiene(root, rep)
    if selected(args.targets, "global"):
        check_global_state(root, rep)
    for project in manifest.projects:
        if not (selected(args.targets, project.name) and project.is_symlink_mode):
            continue
        if project.parent_declared and project.parent.is_dir():
            check_project_state(project, root, rep)
    return rep.summary("check")


# --------------------------------------------------------------------- list --


def skill_description(skill_md: Path) -> str:
    """The skill's `description:` value, truncated for the inventory column."""
    if not skill_md.is_file():
        return ""
    for line in skill_md.read_text(encoding="utf-8").splitlines():
        if line.startswith("description:"):
            return truncate_bytes(re.sub(r"^description:[ \t]*", "", line), 100)
    return ""


def list_tier(label: str, claude_md: Path, skills_dir: Path, rep: Reporter) -> None:
    """Print one tier: its CLAUDE.md, then each skill with its description."""
    rep.say(label)
    if claude_md.is_file():
        rep.ok(f"CLAUDE.md ({line_count(claude_md)} lines)")
    else:
        rep.warn("no CLAUDE.md")
    skills = subdirs(skills_dir)
    for skill in skills:
        print(f"      {skill.name:<34} {skill_description(skill / 'SKILL.md')}…", file=rep.out)
    if not skills:
        print("      (no skills yet)", file=rep.out)


def cmd_list(args: argparse.Namespace, rep: Reporter) -> int:
    """list — inventory of managed CLAUDE.md files and skills, by tier."""
    root = repo_root()
    manifest = load_manifest(root / "projects.toml")
    list_tier("global → ~/.claude", root / "global/CLAUDE.md", root / "global/skills", rep)
    for project in manifest.projects:
        if project.mode == "committed":
            rep.say(
                f"{project.name} → {project.parent_raw}  "
                f"(committed mode: config lives in that repo; not managed here)"
            )
            continue
        repo_dir = root / "projects" / project.name
        list_tier(
            f"{project.name} → {project.parent_raw}",
            repo_dir / "CLAUDE.md",
            repo_dir / "claude" / "skills",
            rep,
        )
    return 0


# -------------------------------------------------------------------- probe --


@dataclass(frozen=True)
class ProbeLocation:
    """One scope to interrogate with live sessions, and what it must show."""

    label: str
    cwd: Path
    expect_skills: tuple[str, ...]  # managed names that MUST be visible
    absent_skills: tuple[str, ...]  # names unique to other projects
    marker: str  # this scope's own PROBE-MARKER
    live_claude_md: Path | None  # where that marker must already be deployed
    foreign_markers: tuple[str, ...]


def marker_of(scope: str) -> str:
    return f"{MARKER_PREFIX}{scope}"


def foreign_skills(
    all_project_skills: Iterable[str], own: Iterable[str], global_: Iterable[str]
) -> list[str]:
    """Skill names a scope must NOT see: other projects' minus its own and global.

    Never an exact-set assertion — sessions always see harness and plugin
    skills this repo does not manage.
    """
    return sorted(set(all_project_skills) - set(own) - set(global_))


@dataclass(frozen=True)
class SessionResult:
    """One `claude -p` call: its exit status and combined output."""

    returncode: int
    text: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def first_line(self) -> str:
        lines = self.text.splitlines()
        return lines[0][:200] if lines else "(no output)"


def probe_session(cwd: Path, prompt: str, model: str) -> SessionResult:
    """One real `claude -p` call in `cwd`, stdout+stderr, stdin closed.

    The status matters as much as the text: a failed or auth-expired session
    prints an error message, and scoring that message as a probe answer would
    let a broken run look like a verified one.
    """
    try:
        proc = subprocess.run(
            ["claude", "--model", model, "-p", prompt],
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise Fatal("claude is not on PATH — probe needs a real CLI session") from None
    return SessionResult(proc.returncode, proc.stdout.rstrip("\n"))


def session_failure(label: str, session: SessionResult) -> str:
    """The ✗ line for a `claude -p` call that did not succeed."""
    return f"[{label}] claude -p failed (exit {session.returncode}): {session.first_line}"


def probe_location(location: ProbeLocation, model: str, rep: Reporter) -> int:
    """Run both probes for one scope; return the number of `claude` calls made."""
    if not location.cwd.is_dir():
        rep.fail(f"[{location.label}] cwd missing: {location.cwd}")
        return 0

    rep.say(f"[{location.label}] skills probe from {location.cwd}")
    session = probe_session(location.cwd, SKILLS_PROMPT, model)
    if not session.ok:
        rep.fail(session_failure(location.label, session))
        return 1
    # Skill names are matched against whole (trimmed) lines: one managed
    # name can be a substring of another (agda-typecheck vs
    # agda-typecheck-performance), so substring matching would produce
    # false leak reports. The marker checks below stay substring-based on
    # purpose; the model may quote a marker line inside other text.
    out_names = {line.strip().lstrip("-*• \t") for line in session.text.splitlines()}
    for skill in location.expect_skills:
        if skill in out_names:
            rep.ok(f"[{location.label}] skill visible: {skill}")
        else:
            rep.fail(f"[{location.label}] managed skill MISSING: {skill}")
    for skill in location.absent_skills:
        if skill in out_names:
            rep.fail(f"[{location.label}] foreign skill LEAKED: {skill}")
        else:
            rep.ok(f"[{location.label}] foreign skill absent: {skill}")

    rep.say(f"[{location.label}] CLAUDE.md marker probe")
    session = probe_session(location.cwd, MARKER_PROMPT, model)
    if not session.ok:
        rep.fail(session_failure(location.label, session))
        return 2
    out = session.text
    live = location.live_claude_md
    if live and live.exists() and location.marker in live.read_text(encoding="utf-8"):
        if location.marker in out:
            rep.ok(f"[{location.label}] own CLAUDE.md marker quoted")
        else:
            rep.fail(f"[{location.label}] own CLAUDE.md marker NOT quoted ({location.marker})")
    else:
        rep.warn(
            f"[{location.label}] marker not deployed in live CLAUDE.md yet "
            f"— skipped (pre-migration)"
        )
    for marker in location.foreign_markers:
        if marker in out:
            rep.fail(f"[{location.label}] FOREIGN marker leaked: {marker}")
        else:
            rep.ok(f"[{location.label}] foreign marker absent: {marker}")
    return 2


def probe_locations(root: Path, manifest: Manifest, targets: Sequence[str]) -> list[ProbeLocation]:
    """Build every selected scope's expectations FROM THE REPO, not a fixed list."""
    global_skills = [d.name for d in subdirs(root / "global" / "skills")]
    managed = [p for p in manifest.projects if p.is_symlink_mode]
    project_skills = {
        p.name: [d.name for d in subdirs(root / "projects" / p.name / "claude" / "skills")]
        for p in managed
    }
    everything = sorted({name for names in project_skills.values() for name in names})

    def foreign_markers(own: str) -> tuple[str, ...]:
        return tuple(marker_of(p.name) for p in managed if p.name != own)

    locations = []
    if selected(targets, "global"):
        locations.append(
            ProbeLocation(
                label="global",
                cwd=home(),
                expect_skills=tuple(global_skills),
                absent_skills=tuple(foreign_skills(everything, [], global_skills)),
                marker=marker_of("global"),
                live_claude_md=home() / ".claude/CLAUDE.md",
                foreign_markers=foreign_markers(""),
            )
        )
    for project in managed:
        if not selected(targets, project.name):
            continue
        own = project_skills[project.name]
        locations.append(
            ProbeLocation(
                label=project.name,
                cwd=project.main_checkout,
                expect_skills=tuple(own + global_skills),
                absent_skills=tuple(foreign_skills(everything, own, global_skills)),
                marker=marker_of(project.name),
                live_claude_md=project.parent / "CLAUDE.md",
                foreign_markers=foreign_markers(project.name),
            )
        )
    return locations


def cmd_probe(args: argparse.Namespace, rep: Reporter) -> int:
    """probe — the LIVE verification matrix: 2 real `claude -p` calls per scope."""
    root = repo_root()
    manifest = load_manifest(root / "projects.toml")
    model = os.environ.get("CLAUDE_PROBE_MODEL", "haiku")
    validate_targets(args.targets, ("global", *manifest.names))

    rep.say(f"probe model: {model}   (each location = 2 claude -p calls)")
    locations = probe_locations(root, manifest, args.targets)
    calls = sum(probe_location(location, model, rep) for location in locations)
    rep.say(f"total claude calls: {calls} (model: {model})")
    return rep.summary("probe")


# --------------------------------------------------------- verify-discovery --

FIXTURE_SKILL = "claude-tooling-probe-skill"
FIXTURE_MARKER = "claude-tooling-verify-discovery"
FIXTURE_SKILL_MD = f"""---
name: {FIXTURE_SKILL}
description: Probe fixture verifying skill discovery through per-skill symlinks. Never invoke it; it does nothing.
---
This skill exists only so probe sessions can list it.
"""
# The marker must be a VISIBLE line: HTML comments are stripped from CLAUDE.md
# before injection (verified empirically, claude 2.1.221) — which is exactly
# what this fixture guards.
FIXTURE_CLAUDE_MD = f"""# probeproj

Probe fixture project.

PROBE-MARKER: {FIXTURE_MARKER}
"""


def build_discovery_fixture(scratch: Path) -> Path:
    """Build the deployment shape under test, and return the project parent.

        store/projects/probeproj/claude/skills/<skill>/   (stand-in for this repo)
        probeproj/                                        (project parent dir)
          CLAUDE.md          -> store copy                (symlinked parent file)
          .claude/           real dir
            skills/<skill>   -> store copy                (PER-SKILL symlink)
          main/              git repo;  .claude -> ../.claude
          worktrees/wt1/     linked worktree;  .claude -> ../../.claude
    """
    store = scratch / "store/projects/probeproj"
    parent = scratch / "probeproj"
    shutil.rmtree(store, ignore_errors=True)
    shutil.rmtree(parent, ignore_errors=True)
    (store / "claude/skills" / FIXTURE_SKILL).mkdir(parents=True)
    parent.mkdir(parents=True)

    skill_dir = store / "claude/skills" / FIXTURE_SKILL
    (skill_dir / "SKILL.md").write_text(FIXTURE_SKILL_MD, encoding="utf-8")
    (store / "CLAUDE.md").write_text(FIXTURE_CLAUDE_MD, encoding="utf-8")

    (parent / "CLAUDE.md").symlink_to(store / "CLAUDE.md")
    (parent / ".claude/skills").mkdir(parents=True)
    (parent / ".claude/skills" / FIXTURE_SKILL).symlink_to(store / "claude/skills" / FIXTURE_SKILL)

    main = parent / "main"
    main.mkdir()

    def run(*args: str) -> None:
        subprocess.run(args, cwd=main, check=True, capture_output=True)

    run("git", "init", "-q", "-b", "main", ".")
    (main / "README").write_text("probe\n", encoding="utf-8")
    run("git", "add", "README")
    identity = ("-c", "user.email=probe@localhost", "-c", "user.name=probe")
    run("git", *identity, "commit", "-qm", "probe")
    with (main / ".git/info/exclude").open("a", encoding="utf-8") as handle:
        handle.write("/.claude\n")
    run("git", "worktree", "add", "-q", "-b", "wt1", "../worktrees/wt1")

    (main / ".claude").symlink_to(parent / ".claude")
    (parent / "worktrees/wt1/.claude").symlink_to(parent / ".claude")
    return parent


def discovery_case(label: str, cwd: Path, model: str, rep: Reporter) -> None:
    """Ask one fixture session for its skills and its markers, and judge both."""
    rep.say(f"[{label}] asking for skill list …")
    session = probe_session(cwd, SKILLS_PROMPT, model)
    for line in session.text.split("\n"):
        print(f"      {line}", file=rep.out)
    if not session.ok:
        rep.fail(session_failure(label, session))
        return
    if FIXTURE_SKILL in session.text:
        rep.ok(f"[{label}] skill visible through per-skill symlink")
    else:
        rep.fail(f"[{label}] skill NOT visible through per-skill symlink")

    rep.say(f"[{label}] asking for CLAUDE.md marker …")
    session = probe_session(cwd, MARKER_PROMPT, model)
    for line in session.text.split("\n"):
        print(f"      {line}", file=rep.out)
    if not session.ok:
        rep.fail(session_failure(label, session))
    elif FIXTURE_MARKER in session.text:
        rep.ok(f"[{label}] symlinked parent CLAUDE.md loaded via ancestor traversal")
    else:
        rep.fail(f"[{label}] symlinked parent CLAUDE.md NOT loaded")


def cmd_verify_discovery(args: argparse.Namespace, rep: Reporter) -> int:
    """verify-discovery — re-verify the discovery rules this design rests on."""
    model = os.environ.get("CLAUDE_PROBE_MODEL", "haiku")
    scratch = Path(args.scratch_dir) if args.scratch_dir else Path(
        tempfile.mkdtemp(prefix="claude-tooling-verify.")
    )
    scratch.mkdir(parents=True, exist_ok=True)
    scratch = scratch.resolve()
    rep.say(f"scratch dir: {scratch}  (model: {model})")

    parent = build_discovery_fixture(scratch)
    discovery_case("worktree", parent / "worktrees/wt1", model, rep)
    discovery_case("main-checkout", parent / "main", model, rep)

    version = subprocess.run(
        ["claude", "--version"], capture_output=True, text=True, check=False
    ).stdout.splitlines()
    rep.say(f"claude version: {version[0] if version else ''}")
    return rep.summary("verify-discovery")


# -------------------------------------------------------------- add-project --

STUB_CLAUDE_MD = """# {name} — working conventions

(Write the project conventions here: build/test commands, layout, git
workflow, style. This file loads into every Claude session under
{parent}/ via ancestor traversal.)

## Claude config for this project

Managed in williamdemeo/claude-tooling (projects/{name}/) and symlinked into
place; project skills belong there, not in ~/.claude/skills/.

{marker}
"""

STANZA = """
[projects."{name}"]
parent = "{parent}"
main   = "{main}"
mode   = "symlink"
"""

# A single plain path component: no separators, no leading dot, so it cannot
# be `.`, `..`, or anything that walks out of projects/.
COMPONENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def split_spec(spec: str) -> tuple[str, str]:
    """`<org>/<name>` → (org, name), rejecting anything else.

    Splitting on the first slash alone would accept `org/../../elsewhere`,
    and `projects/<name>` would then escape the repo entirely; `org/a/b`
    would quietly scaffold a nested directory and an unusable stanza.
    """
    parts = spec.split("/")
    if len(parts) != 2 or not all(COMPONENT_RE.match(part) for part in parts):
        raise Fatal(f"expected <org>/<name> — two plain names, no path separators: {spec}")
    return parts[0], parts[1]


def cmd_add_project(args: argparse.Namespace, rep: Reporter) -> int:
    """add-project — scaffold a new symlink-mode project and its manifest stanza."""
    root = repo_root()
    manifest_path = root / "projects.toml"
    manifest = load_manifest(manifest_path)

    org, name = split_spec(args.spec)
    if not COMPONENT_RE.match(args.main):
        raise Fatal(f"--main must be a plain directory name: {args.main}")
    parent_raw = args.parent or f"~/git/{org}/{name}"
    repo_dir = root / "projects" / name

    rep.say(f"scaffolding project '{name}'  (parent: {parent_raw}, main: {args.main})")
    if name in manifest.names:
        raise Fatal(f"project '{name}' already in {manifest_path}")
    if repo_dir.exists():
        raise Fatal(f"projects/{name} already exists in the repo")
    if '"' in parent_raw:
        raise Fatal("the parent path must not contain double quotes")

    parent_abs = Path(expand_tilde(parent_raw))
    if not parent_abs.is_dir():
        rep.warn(f"parent dir does not exist yet: {parent_abs}")
    if not (parent_abs / args.main).is_dir():
        rep.warn(f"main checkout does not exist yet: {parent_abs}/{args.main}")

    (repo_dir / "claude/skills").mkdir(parents=True)
    (repo_dir / "claude/skills/.gitkeep").touch()
    rep.ok(f"created projects/{name}/claude/skills/")

    (repo_dir / "CLAUDE.md").write_text(
        STUB_CLAUDE_MD.format(name=name, parent=parent_raw, marker=marker_of(name)),
        encoding="utf-8",
    )
    rep.ok(f"created projects/{name}/CLAUDE.md (stub)")

    with manifest_path.open("a", encoding="utf-8") as handle:
        handle.write(STANZA.format(name=name, parent=parent_raw, main=args.main))
    rep.ok("appended manifest stanza to projects.toml")

    rep.say("next steps")
    print(f"  1. edit projects/{name}/CLAUDE.md", file=rep.out)
    print(f"  2. add skills under projects/{name}/claude/skills/<skill>/SKILL.md", file=rep.out)
    print("  3. make check", file=rep.out)
    print(f"  4. make install PROJECT={name}   (then: make probe PROJECT={name})", file=rep.out)
    return rep.summary("add-project")


# ---------------------------------------------------------------------- cli --


def build_parser() -> argparse.ArgumentParser:
    """The subcommand surface; the `*.sh` shims map one-to-one onto it."""
    parser = argparse.ArgumentParser(
        prog="ct.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(
        name: str, handler: Callable[[argparse.Namespace, Reporter], int], help_text: str
    ) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        sub.set_defaults(func=handler)
        return sub

    install = add("install", cmd_install, "deploy config from this repo via symlinks")
    install.add_argument(
        "--dry-run", action="store_true", help="print what would change; touch nothing"
    )
    install.add_argument(
        "--force", action="store_true", help="replace real files (backed up first)"
    )
    install.add_argument(
        "targets", nargs="*", metavar="global|<project>", help="default: everything"
    )

    link = add("link-worktrees", cmd_link_worktrees, "backfill root .claude links over worktrees")
    link.add_argument("--dry-run", action="store_true")
    link.add_argument("--force", action="store_true")
    link.add_argument("--all", action="store_true", help="every project in the manifest")
    link.add_argument("targets", nargs="*", metavar="<project>")

    check = add("check", cmd_check, "static verification: manifest, hygiene, link state")
    check.add_argument("targets", nargs="*", metavar="global|<project>", help="default: everything")

    add("list", cmd_list, "inventory of managed CLAUDE.md files and skills by tier")

    lint = add("lint", cmd_lint, "repo hygiene: skills frontmatter, stale paths, markers")
    lint.add_argument("root", nargs="?", help="repo root (default: this checkout)")

    probe = add("probe", cmd_probe, "LIVE verification matrix (spawns claude -p; costs tokens)")
    probe.add_argument("targets", nargs="*", metavar="global|<project>", help="default: everything")

    verify = add(
        "verify-discovery", cmd_verify_discovery, "re-verify discovery rules with fixtures"
    )
    verify.add_argument("scratch_dir", nargs="?", help="scratch dir (default: a fresh temp dir)")

    new = add("add-project", cmd_add_project, "scaffold a new symlink-mode project")
    new.add_argument("spec", metavar="<org>/<name>")
    new.add_argument("--parent", help="override the parent dir (default ~/git/<org>/<name>)")
    new.add_argument("--main", default="main", help="main-checkout dir name (default: main)")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run the subcommand, and turn a Fatal into a ✗ + exit 1."""
    if isinstance(sys.stdout, io.TextIOWrapper):  # markers are UTF-8 even in a C locale
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    rep = Reporter()
    try:
        return int(args.func(args, rep))
    except Fatal as exc:
        rep.fail(str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
