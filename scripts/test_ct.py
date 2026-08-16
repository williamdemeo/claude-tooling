#!/usr/bin/env python3
"""Tests for ct.py — stdlib `unittest`, no network, no live config.

Everything runs against throwaway fixtures under a temp dir: the end-to-end
cases copy ct.py into a fake repo and run it with `$HOME` pointed at the
fixture, so a bug here can never reach the real `~/.claude`.

    make test        # or: python3 -m unittest discover -s scripts -q
"""

import io
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import ct  # noqa: E402


def write(path: Path, text: str) -> Path:
    """Create `path` (and its parents) holding dedented `text`."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text), encoding="utf-8")
    return path


class TempDirCase(unittest.TestCase):
    """A test with its own scratch directory, removed afterwards."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ct-test."))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)


def capture() -> tuple[ct.Reporter, io.StringIO]:
    """A Reporter writing to a buffer, with colors off."""
    buffer = io.StringIO()
    return ct.Reporter(buffer, ct.Palette()), buffer


# --------------------------------------------------------------- reporting --


class ReporterTest(unittest.TestCase):
    def test_markers_and_counts(self) -> None:
        rep, buffer = capture()
        rep.say("header")
        rep.ok("fine")
        rep.plan("would do")
        rep.warn("expected")
        rep.attn("look at me")
        rep.fail("broken")
        self.assertEqual(
            buffer.getvalue().splitlines(),
            [
                ":: header",
                "  ✓ fine",
                "  → would do",
                "  ! expected",
                "  !! look at me",
                "  ✗ broken",
            ],
        )
        self.assertEqual((rep.n_ok, rep.n_plan, rep.n_warn, rep.n_attn, rep.n_err), (1, 1, 1, 1, 1))

    def test_summary_recaps_attention_verbatim(self) -> None:
        rep, buffer = capture()
        rep.attn("real file/dir in the way")
        self.assertEqual(rep.summary("install"), 0)  # !! alone is not an error
        lines = buffer.getvalue().splitlines()
        self.assertEqual(lines[0], "  !! real file/dir in the way")
        self.assertEqual(lines[1], "")
        self.assertEqual(lines[2], ":: NEEDS ATTENTION (1) — investigate before proceeding:")
        self.assertEqual(lines[3], "  !! real file/dir in the way")
        self.assertEqual(lines[4], ":: install: 0 ok, 0 warnings, 1 NEED ATTENTION, 0 errors")

    def test_summary_counts_planned_only_when_present(self) -> None:
        rep, buffer = capture()
        rep.ok("a")
        self.assertEqual(rep.summary("check"), 0)
        self.assertEqual(buffer.getvalue().splitlines()[-1], ":: check: 1 ok, 0 warnings, 0 errors")
        rep.plan("b")
        rep.summary("check")
        self.assertEqual(
            buffer.getvalue().splitlines()[-1], ":: check: 1 ok, 1 planned, 0 warnings, 0 errors"
        )

    def test_only_hard_errors_are_nonzero(self) -> None:
        rep, _ = capture()
        rep.warn("pending")
        self.assertEqual(rep.summary("check"), 0)
        rep.fail("broken")
        self.assertEqual(rep.summary("check"), 1)

    def test_palette_is_empty_without_a_tty(self) -> None:
        self.assertEqual(ct.Palette.for_stream(io.StringIO()), ct.Palette())


# ---------------------------------------------------------------- manifest --

MANIFEST = """\
    [meta]
    canonical_root = "~/git/williamdemeo/claude-tooling/main"

    [projects.fls]
    parent = "~/git/IO/fls"
    main   = "master"
    mode   = "symlink"

    [projects."williamdemeo.github.io"]
    parent = "~/git/williamdemeo/williamdemeo.github.io"

    [projects.github-project]
    parent = "~/git/williamdemeo/github-project"
    mode   = "committed"
"""


class ManifestTest(TempDirCase):
    def load(self, text: str = MANIFEST) -> ct.Manifest:
        return ct.load_manifest(write(self.tmp / "projects.toml", text))

    def test_names_are_sorted_and_dotted_names_survive(self) -> None:
        self.assertEqual(self.load().names, ("fls", "github-project", "williamdemeo.github.io"))

    def test_defaults_are_main_and_symlink(self) -> None:
        site = self.load().get("williamdemeo.github.io")
        assert site is not None
        self.assertEqual((site.main, site.mode), ("main", "symlink"))

    def test_tilde_expansion_keeps_the_raw_form_too(self) -> None:
        with mock.patch.dict(os.environ, {"HOME": "/home/fixture"}):
            fls = self.load().get("fls")
        assert fls is not None
        self.assertEqual(fls.parent_raw, "~/git/IO/fls")
        self.assertEqual(fls.parent, Path("/home/fixture/git/IO/fls"))
        self.assertEqual(fls.main_checkout, Path("/home/fixture/git/IO/fls/master"))

    def test_meta_and_modes(self) -> None:
        manifest = self.load()
        self.assertEqual(manifest.canonical_root, "~/git/williamdemeo/claude-tooling/main")
        product = manifest.get("github-project")
        assert product is not None
        self.assertFalse(product.is_symlink_mode)

    def test_real_toml_features_the_awk_subset_could_not_handle(self) -> None:
        # A '#' inside a value was forbidden by the old awk parser's caveat.
        manifest = self.load('[projects.p]\nparent = "/tmp/a#b"  # trailing comment\n')
        project = manifest.get("p")
        assert project is not None
        self.assertEqual(project.parent_raw, "/tmp/a#b")

    def test_missing_file_and_bad_toml_are_fatal(self) -> None:
        with self.assertRaises(ct.Fatal):
            ct.load_manifest(self.tmp / "nope.toml")
        with self.assertRaises(ct.Fatal):
            self.load("[projects.p]\nparent = oops\n")

    def test_non_string_value_is_fatal(self) -> None:
        with self.assertRaises(ct.Fatal):
            self.load('[projects.p]\nparent = ["a", "b"]\n')

    def test_a_stanza_without_a_parent_is_not_the_current_directory(self) -> None:
        # Path("") is Path("."): nothing may act on such a project, or the
        # installer would deploy into whatever directory it was run from.
        project = self.load('[projects.p]\nmain = "main"\n').get("p")
        assert project is not None
        self.assertFalse(project.parent_declared)

    def test_a_relative_parent_is_also_refused(self) -> None:
        project = self.load('[projects.p]\nparent = "relative/path"\n').get("p")
        assert project is not None
        self.assertFalse(project.parent_declared)

    def test_an_absolute_parent_is_declared(self) -> None:
        project = self.load('[projects.p]\nparent = "/abs/path"\n').get("p")
        assert project is not None
        self.assertTrue(project.parent_declared)

    def test_an_unknown_mode_is_fatal_at_load(self) -> None:
        # Not every command runs check's layers: install would treat a typo'd
        # mode as symlink mode and manage a project meant to be untouched.
        with self.assertRaises(ct.Fatal) as caught:
            self.load('[projects.p]\nparent = "/p"\nmode = "committted"\n')
        self.assertIn("mode", str(caught.exception))

    def test_main_must_be_a_plain_directory_name(self) -> None:
        # A separator or leading dot would escape `parent` via Path joining
        # (an absolute `main` REPLACES parent entirely: Path("/p") / "/etc").
        for bad in ("../elsewhere", "/etc", "a/b", ".hidden", ""):
            with self.assertRaises(ct.Fatal, msg=repr(bad)):
                self.load(f'[projects.p]\nparent = "/p"\nmain = "{bad}"\n')

    def test_project_names_are_validated_like_main(self) -> None:
        # Keys join onto root/"projects": TOML quoted keys make
        # [projects."/tmp"] parseable, and Path would discard the repo
        # prefix and manage files outside the repository.
        for bad in ("/tmp", "../x", "a/b", ".hidden"):
            with self.assertRaises(ct.Fatal, msg=repr(bad)):
                self.load(f'[projects."{bad}"]\nparent = "/p"\n')

    def test_global_is_a_reserved_project_name(self) -> None:
        # `install global` etc. would select both the global tier and the
        # project; probe builds its global location from the same word.
        with self.assertRaises(ct.Fatal) as caught:
            self.load('[projects.global]\nparent = "/p"\n')
        self.assertIn("reserved", str(caught.exception))


class ValidateTargetsTest(unittest.TestCase):
    def test_known_targets_pass(self) -> None:
        ct.validate_targets(["global", "fls"], ["global", "fls", "other"])
        ct.validate_targets([], ["global"])  # no targets = everything

    def test_a_typo_is_fatal_rather_than_a_silent_no_op(self) -> None:
        with self.assertRaises(ct.Fatal) as caught:
            ct.validate_targets(["flss"], ["global", "fls"])
        self.assertIn("unknown target(s): flss", str(caught.exception))
        self.assertIn("known: fls global", str(caught.exception))


class SelectionTest(unittest.TestCase):
    def test_no_targets_selects_everything(self) -> None:
        self.assertTrue(ct.selected([], "fls"))

    def test_targets_are_exact_names(self) -> None:
        self.assertTrue(ct.selected(["global", "fls"], "fls"))
        self.assertFalse(ct.selected(["global"], "fls"))
        self.assertFalse(ct.selected(["fl"], "fls"))


class TildeTest(unittest.TestCase):
    def test_expansion_matches_the_shell(self) -> None:
        with mock.patch.dict(os.environ, {"HOME": "/home/fixture"}):
            self.assertEqual(ct.expand_tilde("~"), "/home/fixture")
            self.assertEqual(ct.expand_tilde("~/git/x"), "/home/fixture/git/x")
            self.assertEqual(ct.expand_tilde("~other/git"), "~other/git")
            self.assertEqual(ct.expand_tilde("/abs/path"), "/abs/path")


# ------------------------------------------------------ filesystem helpers --


class GlobHelpersTest(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        for name in ("beta", "alpha", ".hidden"):
            (self.tmp / name).mkdir()
        (self.tmp / "file.txt").touch()
        (self.tmp / ".dotfile").touch()
        (self.tmp / "..odd").touch()
        (self.tmp / "dangling").symlink_to(self.tmp / "gone")
        (self.tmp / "linked").symlink_to(self.tmp / "alpha")

    def test_subdirs_are_sorted_dirs_only_and_follow_symlinks(self) -> None:
        self.assertEqual([p.name for p in ct.subdirs(self.tmp)], ["alpha", "beta", "linked"])

    def test_members_skip_dotfiles_and_dangling_symlinks(self) -> None:
        self.assertEqual(
            [p.name for p in ct.members(self.tmp)], ["alpha", "beta", "file.txt", "linked"]
        )

    def test_glob_entries_lists_visible_then_dotted(self) -> None:
        names = [p.name for p in ct.glob_entries(self.tmp)]
        self.assertEqual(
            names, ["alpha", "beta", "dangling", "file.txt", "linked", ".dotfile", ".hidden"]
        )
        self.assertNotIn("..odd", names)  # the shell's .[!.]* excludes it

    def test_helpers_tolerate_a_missing_directory(self) -> None:
        gone = self.tmp / "gone"
        self.assertEqual((ct.subdirs(gone), ct.members(gone), ct.glob_entries(gone)), ([], [], []))


class SmallHelpersTest(TempDirCase):
    def test_points_into(self) -> None:
        self.assertTrue(ct.points_into("/repo/global/x", Path("/repo")))
        self.assertFalse(ct.points_into("/repo-other/x", Path("/repo")))
        self.assertFalse(ct.points_into("/repo", Path("/repo")))

    def test_relative_label(self) -> None:
        self.assertEqual(ct.relative_label(Path("/p/worktrees/a"), Path("/p")), "worktrees/a")
        self.assertEqual(ct.relative_label(Path("/elsewhere/a"), Path("/p")), "/elsewhere/a")

    def test_line_count_matches_wc_l(self) -> None:
        path = write(self.tmp / "f.md", "a\nb\nc\n")
        self.assertEqual(ct.line_count(path), 3)
        self.assertEqual(ct.line_count(write(self.tmp / "g.md", "no trailing newline")), 0)

    def test_truncate_bytes_never_splits_a_character(self) -> None:
        text = "x" * 98 + "—y"  # the em dash straddles byte 99
        self.assertEqual(ct.truncate_bytes(text, 100), "x" * 98)
        self.assertEqual(ct.truncate_bytes("short", 100), "short")


# ---------------------------------------------------------------- linking ---


class PlanLinkTest(TempDirCase):
    def test_correct_symlink_is_ok(self) -> None:
        link = self.tmp / "l"
        link.symlink_to("/target")
        self.assertEqual(ct.plan_link("/target", link, force=False), ct.LinkPlan("ok", "/target"))

    def test_wrong_symlink_is_a_repoint_by_string_comparison(self) -> None:
        link = self.tmp / "l"
        link.symlink_to("/other")
        # Same file, different spelling: still a re-point — comparison is textual.
        self.assertEqual(ct.plan_link("/target", link, force=False).action, "repoint")

    def test_dangling_symlink_is_still_judged_as_a_symlink(self) -> None:
        link = self.tmp / "l"
        link.symlink_to(self.tmp / "gone")
        self.assertEqual(ct.plan_link("/target", link, force=False).action, "repoint")

    def test_real_file_blocks_unless_forced(self) -> None:
        link = self.tmp / "real"
        link.touch()
        self.assertEqual(ct.plan_link("/target", link, force=False).action, "blocked")
        self.assertEqual(ct.plan_link("/target", link, force=True).action, "replace")

    def test_absent_is_a_create(self) -> None:
        self.assertEqual(ct.plan_link("/t", self.tmp / "nope", force=False).action, "create")


class EnsureLinkTest(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.target = self.tmp / "target"
        self.target.mkdir()
        self.opts = ct.Options(
            backup_root=self.tmp / "backups", backup_stamp="20260809-000000"
        )

    def run_link(self, link: Path, **kwargs: bool) -> tuple[ct.Reporter, str]:
        rep, buffer = capture()
        opts = ct.Options(
            dry_run=kwargs.get("dry_run", False),
            force=kwargs.get("force", False),
            backup_root=self.opts.backup_root,
            backup_stamp=self.opts.backup_stamp,
        )
        ct.ensure_link(str(self.target), link, "desc", rep, opts)
        return rep, buffer.getvalue()

    def test_creates_missing_parents(self) -> None:
        link = self.tmp / "deep/nest/link"
        rep, out = self.run_link(link)
        self.assertEqual(os.readlink(link), str(self.target))
        self.assertEqual((rep.n_ok, out.strip()), (1, "✓ desc — linked"))

    def test_dry_run_touches_nothing(self) -> None:
        link = self.tmp / "link"
        rep, out = self.run_link(link, dry_run=True)
        self.assertFalse(link.exists())
        self.assertEqual(rep.n_plan, 1)
        self.assertIn(f"→ desc — would link → {self.target}", out)

    def test_repoint_logs_the_old_target(self) -> None:
        link = self.tmp / "link"
        link.symlink_to("/old/place")
        _, out = self.run_link(link)
        self.assertEqual(os.readlink(link), str(self.target))
        self.assertIn("✓ desc — re-pointed (was → /old/place)", out)

    def test_real_file_needs_attention_and_is_left_alone(self) -> None:
        link = write(self.tmp / "link", "precious\n")
        rep, out = self.run_link(link)
        self.assertEqual(link.read_text(), "precious\n")
        self.assertEqual(rep.n_attn, 1)
        self.assertIn("!! desc — real file/dir in the way; skipped", out)
        self.assertEqual(rep.attn_lines[0][:4], "desc")

    def test_force_moves_the_original_into_the_central_backup_tree(self) -> None:
        link = write(self.tmp / "link", "precious\n")
        _, out = self.run_link(link, force=True)
        backup = self.opts.backup_root / f"20260809-000000{link}"
        self.assertEqual(backup.read_text(), "precious\n")
        self.assertEqual(os.readlink(link), str(self.target))
        self.assertIn(f"backup: {backup}", out)

    def test_dry_run_with_force_promises_but_does_not_back_up(self) -> None:
        link = write(self.tmp / "link", "precious\n")
        rep, out = self.run_link(link, dry_run=True, force=True)
        self.assertEqual(link.read_text(), "precious\n")
        self.assertFalse(self.opts.backup_root.exists())
        self.assertEqual(rep.n_plan, 1)
        self.assertIn("would replace real file/dir", out)


class EnsureRealdirTest(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        (self.root / "projects").mkdir(parents=True)

    def plan(self, directory: Path) -> ct.DirPlan:
        return ct.plan_realdir(directory, self.root)

    def test_repo_pointing_symlink_is_the_legacy_whole_dir_scheme(self) -> None:
        link = self.tmp / "dot-claude"
        link.symlink_to(self.root / "projects")
        self.assertEqual(self.plan(link).action, "repo_link")
        rep, _ = capture()
        ct.ensure_realdir(link, "d", self.root, rep, ct.Options())
        self.assertTrue(link.is_dir() and not link.is_symlink())

    def test_foreign_symlink_needs_force(self) -> None:
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        link = self.tmp / "dot-claude"
        link.symlink_to(elsewhere)
        self.assertEqual(self.plan(link).action, "foreign_link")

        rep, buffer = capture()
        ct.ensure_realdir(link, "d", self.root, rep, ct.Options())
        self.assertTrue(link.is_symlink())
        self.assertEqual(rep.n_attn, 1)
        self.assertIn("!! d — is a symlink", buffer.getvalue())

        rep, _ = capture()
        ct.ensure_realdir(link, "d", self.root, rep, ct.Options(force=True))
        self.assertTrue(link.is_dir() and not link.is_symlink())

    def test_plain_file_is_an_error(self) -> None:
        path = write(self.tmp / "file", "x")
        self.assertEqual(self.plan(path).action, "not_a_dir")
        rep, _ = capture()
        ct.ensure_realdir(path, "d", self.root, rep, ct.Options())
        self.assertEqual(rep.n_err, 1)

    def test_real_dir_and_absent(self) -> None:
        real = self.tmp / "real"
        real.mkdir()
        self.assertEqual(self.plan(real).action, "ok")
        self.assertEqual(self.plan(self.tmp / "absent").action, "create")

    def test_the_return_value_tells_the_caller_whether_to_go_on(self) -> None:
        # False means: do not link anything underneath this path.
        elsewhere = self.tmp / "elsewhere"
        elsewhere.mkdir()
        foreign = self.tmp / "foreign"
        foreign.symlink_to(elsewhere)
        file_in_the_way = write(self.tmp / "file", "x")
        real = self.tmp / "real"
        real.mkdir()
        repo_link = self.tmp / "repo-link"
        repo_link.symlink_to(self.root / "projects")

        def established(path: Path, dry_run: bool = False, force: bool = False) -> bool:
            rep, _ = capture()
            options = ct.Options(dry_run=dry_run, force=force)
            return ct.ensure_realdir(path, "d", self.root, rep, options)

        self.assertFalse(established(foreign))
        self.assertFalse(established(file_in_the_way))
        self.assertTrue(established(real))
        self.assertTrue(established(self.tmp / "absent", dry_run=True))
        self.assertTrue(established(repo_link, dry_run=True))
        # --force does establish it, so a --dry-run --force still predicts the
        # child links it would then create.
        self.assertTrue(established(foreign, dry_run=True, force=True))


# ------------------------------------------------------------------- lint --


class FrontmatterTest(unittest.TestCase):
    def test_parses_simple_key_values(self) -> None:
        fields, body = ct.parse_frontmatter("---\nname: a\ndescription: b\n---\nbody\n")
        self.assertEqual(fields, {"name": "a", "description": "b"})
        self.assertEqual(body, "body")

    def test_rejects_missing_unterminated_and_malformed(self) -> None:
        for text in ("no frontmatter\n", "---\nname: a\n", "---\nname: a\nbroken line\n---\n"):
            self.assertIsNone(ct.parse_frontmatter(text)[0], text)


class LintRuleTest(TempDirCase):
    def test_sha_regex_needs_both_a_digit_and_a_letter(self) -> None:
        self.assertTrue(ct.SHA_RE.search("see d1799df for context"))
        self.assertTrue(ct.SHA_RE.search("abc1234"))
        self.assertFalse(ct.SHA_RE.search("deadbeef"))  # no digit
        self.assertFalse(ct.SHA_RE.search("1234567"))  # no letter
        self.assertFalse(ct.SHA_RE.search("abc123"))  # too short

    def test_pr_and_issue_references(self) -> None:
        for text in ("PR #12", "pull request #3", "issue #1", "pull/45"):
            self.assertTrue(ct.PRNUM_RE.search(text), text)
        self.assertFalse(ct.PRNUM_RE.search("chapter 12"))

    def test_stale_paths_ignore_placeholders_and_punctuation(self) -> None:
        real = self.tmp / "real"
        real.mkdir()
        self.assertEqual(ct.stale_paths(f"see {real}."), [])
        self.assertEqual(ct.stale_paths("~/git/<org>/<name>/x"), [])
        self.assertEqual(ct.stale_paths("~/git/$PROJECT/x"), [])
        gone = "/home/williamdemeo/gone-forever/x"
        self.assertEqual(ct.stale_paths(gone), [gone])

    def test_exempt_line_is_skipped_entirely(self) -> None:
        rep, _ = capture()
        ct.lint_body("f.md", "/home/williamdemeo/gone d1799df  (lint-skills: ok)", rep)
        self.assertEqual(rep.n_err, 0)

    def test_trigger_cue_detection(self) -> None:
        self.assertTrue(ct.TRIGGER_CUES.search("Use this when porting a module"))
        self.assertFalse(ct.TRIGGER_CUES.search("A helper for porting modules"))


class LintRepoTest(TempDirCase):
    """The lint over a whole fixture repo — duplicates, names, markers."""

    def build(self, skills: dict[str, list[str]], *, marker: bool = True) -> Path:
        root = self.tmp / "repo"
        body = "PROBE-MARKER: claude-tooling/global\n" if marker else "nothing\n"
        write(root / "global/CLAUDE.md", body)
        for tier, names in skills.items():
            base = (
                root / "global/skills"
                if tier == "global"
                else root / f"projects/{tier}/claude/skills"
            )
            if tier != "global":
                write(
                    root / f"projects/{tier}/CLAUDE.md",
                    f"PROBE-MARKER: claude-tooling/{tier}\n" if marker else "nothing\n",
                )
            for name in names:
                write(
                    base / name / "SKILL.md",
                    f"---\nname: {name}\ndescription: Use this when you need {name}"
                    f" for a long enough description.\n---\nbody\n",
                )
        return root

    def lint(self, root: Path) -> tuple[ct.Reporter, str]:
        rep, buffer = capture()
        ct.run_lint(root, rep)
        return rep, buffer.getvalue()

    def test_clean_repo_passes(self) -> None:
        root = self.build({"global": ["g-one"], "proj-a": ["a-one"]})
        rep, out = self.lint(root)
        self.assertEqual((rep.n_err, rep.n_warn), (0, 0), out)
        self.assertIn("✓ no duplicates in any visible set", out)

    def test_same_name_in_two_projects_is_fine(self) -> None:
        root = self.build({"global": ["g"], "proj-a": ["shared"], "proj-b": ["shared"]})
        rep, out = self.lint(root)
        self.assertEqual(rep.n_err, 0, out)

    def test_global_and_project_clash_is_an_error(self) -> None:
        root = self.build({"global": ["shared"], "proj-a": ["shared"]})
        rep, out = self.lint(root)
        self.assertEqual(rep.n_err, 1)
        self.assertIn("duplicate skill name 'shared' visible in a proj-a session", out)

    def test_name_must_match_directory(self) -> None:
        root = self.build({"global": ["g"]})
        write(
            root / "global/skills/g/SKILL.md",
            "---\nname: other\ndescription: Use this when the name disagrees with its dir.\n---\n",
        )
        rep, out = self.lint(root)
        self.assertIn("does not match directory name", out)
        self.assertEqual(rep.n_err, 1)

    def test_short_description_warns(self) -> None:
        root = self.build({"global": ["g"]})
        write(root / "global/skills/g/SKILL.md", "---\nname: g\ndescription: too short\n---\n")
        rep, out = self.lint(root)
        self.assertIn("description is short", out)
        self.assertEqual((rep.n_err, rep.n_warn), (0, 1))

    def test_missing_visible_marker_warns(self) -> None:
        root = self.build({"global": ["g"], "proj-a": ["a"]}, marker=False)
        rep, out = self.lint(root)
        self.assertEqual(rep.n_warn, 2, out)
        self.assertIn("global/CLAUDE.md: no visible PROBE-MARKER line", out)

    def test_html_commented_marker_does_not_count(self) -> None:
        # HTML comments are stripped from CLAUDE.md before injection.
        root = self.build({"global": ["g"]})
        write(root / "global/CLAUDE.md", "<!-- PROBE-MARKER: claude-tooling/global -->\n")
        rep, _ = self.lint(root)
        self.assertEqual(rep.n_warn, 1)


class SecretScanTest(TempDirCase):
    """The pre-public gate: secret-shaped strings fail wherever a commit
    could reach them. Every fixture token is ASSEMBLED at runtime so this
    file never contains a token-shaped literal that would trip the repo's
    own scan."""

    @staticmethod
    def fake(prefix: str, length: int, fill: str = "A") -> str:
        return prefix + fill * length

    def scan(self, root: Path) -> tuple[ct.Reporter, str]:
        rep, buffer = capture()
        ct.scan_secrets(root, rep)
        return rep, buffer.getvalue()

    def test_token_shapes_are_errors_and_masked(self) -> None:
        root = self.tmp / "r"
        shapes = [
            self.fake("ghp_", 36),
            self.fake("github_pat_", 22),
            self.fake("glpat-", 20),
            self.fake("sk-ant-", 20),
            self.fake("sk-", 24),
            self.fake("AKIA", 16),
            self.fake("AIza", 35),
            self.fake("xoxb-", 12),
            self.fake("xapp-", 12),
            self.fake("npm_", 36),
            self.fake("eyJ", 10) + "." + self.fake("", 12, "B") + "." + self.fake("", 6, "C"),
            self.fake("-----BEGIN RSA PRIVATE ", 0) + self.fake("KEY-----", 0),
            "https://x-access-token:" + self.fake("", 12) + "@github.com/o/r.git",
            "https://user:" + "abcd+ef!" + "@example.com",  # RFC 3986 sub-delims
        ]
        for index, shape in enumerate(shapes):
            write(root / f"f{index}.md", f"leaked: {shape}\n")
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, len(shapes), out)
        for shape in shapes:
            if len(shape) > 20:  # masked: never repeated whole into the report
                self.assertNotIn(shape, out)

    def test_variable_references_and_prose_prefixes_pass(self) -> None:
        root = self.tmp / "r"
        write(
            root / "doc.md",
            "clone via https://x-access-token:${CLAUDE_TOOLING_TOKEN}@github.com/o/r\n"
            "a fine-grained PAT starts with github_pat_ and ghp_ is classic\n"
            "ssh remotes look like git@github.com:o/r.git\n",
        )
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 0, out)

    def test_exempt_line_is_skipped(self) -> None:
        root = self.tmp / "r"
        write(root / "doc.md", f"example: {self.fake('ghp_', 36)}  (lint-skills: ok)\n")
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 0, out)

    def test_a_stray_binary_byte_does_not_hide_an_ascii_token(self) -> None:
        # Decoding is by replacement, never strict: one invalid byte in an
        # otherwise-text file must not exempt the whole file from the gate.
        root = self.tmp / "r"
        root.mkdir(parents=True)
        (root / "blob.bin").write_bytes(b"\xff\xfe" + self.fake("ghp_", 36).encode())
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 1, out)
        self.assertIn("blob.bin", out)

    def test_a_symlink_target_string_is_scanned_not_dereferenced(self) -> None:
        # A commit stores the symlink's TARGET STRING as the blob content;
        # is_file() alone would drop this broken link and never see it.
        root = self.tmp / "r"
        root.mkdir(parents=True)
        (root / "sneaky").symlink_to(self.fake("ghp_", 36))
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 1, out)
        self.assertIn("sneaky (symlink target)", out)

    def test_staged_content_differing_from_the_worktree_is_scanned(self) -> None:
        # A token staged and then wiped from the worktree copy still rides
        # into the next commit; the gate must read the staged blob too.
        root = self.tmp / "r"
        write(root / "clean.md", "nothing\n")
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        write(root / "hook.sh", f"TOKEN={self.fake('ghp_', 36)}\n")
        subprocess.run(["git", "-C", root, "add", "."], check=True, capture_output=True)
        write(root / "hook.sh", "TOKEN=redacted\n")
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 1, out)
        self.assertIn("hook.sh (staged):1", out)

    def test_untracked_files_are_scanned_but_ignored_files_are_not(self) -> None:
        # The scope is "everything a commit could reach": an absorbed-but-
        # not-yet-added copy must be caught; a gitignored scratch file is
        # unreachable by commit and must not block.
        root = self.tmp / "r"
        write(root / "clean.md", "nothing here\n")
        write(root / ".gitignore", "/scratch.txt\n")
        subprocess.run(["git", "init", "-q", root], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", root, "add", "clean.md", ".gitignore"],
            check=True,
            capture_output=True,
        )
        write(root / "untracked.md", f"oops {self.fake('ghp_', 36)}\n")
        write(root / "scratch.txt", f"scratch {self.fake('ghp_', 36)}\n")
        rep, out = self.scan(root)
        self.assertEqual(rep.n_err, 1, out)
        self.assertIn("untracked.md:1", out)
        self.assertNotIn("scratch.txt", out)


# ------------------------------------------------------------------ probe --


class ProbeExpectationTest(unittest.TestCase):
    def test_foreign_skills_are_other_projects_minus_own_and_global(self) -> None:
        everything = ["a-only", "b-only", "shared", "also-global"]
        self.assertEqual(
            ct.foreign_skills(everything, own=["a-only", "shared"], global_=["also-global"]),
            ["b-only"],
        )

    def test_a_scope_owning_everything_expects_no_absences(self) -> None:
        self.assertEqual(ct.foreign_skills(["x"], own=["x"], global_=[]), [])

    def test_global_sees_every_project_skill_as_foreign(self) -> None:
        self.assertEqual(ct.foreign_skills(["b", "a"], own=[], global_=["g"]), ["a", "b"])

    def test_marker_shape(self) -> None:
        self.assertEqual(ct.marker_of("fls"), "PROBE-MARKER: claude-tooling/fls")


class SessionResultTest(unittest.TestCase):
    """A failed `claude -p` must never be scored as a probe answer."""

    def test_nonzero_is_not_ok(self) -> None:
        self.assertFalse(ct.SessionResult(1, "Invalid API key").ok)
        self.assertTrue(ct.SessionResult(0, "agda-typecheck").ok)

    def test_failure_line_quotes_the_status_and_first_line(self) -> None:
        line = ct.session_failure("fls", ct.SessionResult(1, "Invalid API key\nmore"))
        self.assertEqual(line, "[fls] claude -p failed (exit 1): Invalid API key")

    def test_empty_output_still_produces_a_usable_line(self) -> None:
        self.assertIn("(no output)", ct.session_failure("fls", ct.SessionResult(2, "")))

    def test_a_failing_session_is_not_scored_even_if_it_mentions_a_skill(self) -> None:
        # The error text contains the expected token; it must still fail.
        location = ct.ProbeLocation(
            label="fls",
            cwd=Path.cwd(),
            expect_skills=("agda-typecheck",),
            absent_skills=(),
            marker="PROBE-MARKER: claude-tooling/fls",
            live_claude_md=None,
            foreign_markers=(),
        )
        rep, buffer = capture()
        failure = ct.SessionResult(1, "error: agda-typecheck config is invalid")
        with mock.patch.object(ct, "probe_session", return_value=failure):
            calls = ct.probe_location(location, "haiku", rep)
        self.assertEqual(calls, 1)
        self.assertEqual((rep.n_ok, rep.n_err), (0, 1))
        self.assertIn("claude -p failed (exit 1)", buffer.getvalue())


class SkillMatchingTest(unittest.TestCase):
    """Skill names match whole lines; substrings of longer names must not score."""

    def test_a_substring_of_a_longer_name_is_not_a_leak(self) -> None:
        location = ct.ProbeLocation(
            label="agda-algebras",
            cwd=Path.cwd(),
            expect_skills=("agda-typecheck-performance",),
            absent_skills=("agda-typecheck",),
            marker="PROBE-MARKER: claude-tooling/agda-algebras",
            live_claude_md=None,
            foreign_markers=(),
        )
        rep, buffer = capture()
        listing = ct.SessionResult(0, "  - agda-typecheck-performance\nother-skill")
        with mock.patch.object(ct, "probe_session", return_value=listing):
            ct.probe_location(location, "haiku", rep)
        out = buffer.getvalue()
        self.assertIn("skill visible: agda-typecheck-performance", out)
        self.assertIn("foreign skill absent: agda-typecheck", out)
        self.assertEqual(rep.n_err, 0)


class SplitSpecTest(unittest.TestCase):
    def test_accepts_two_plain_names_including_dotted_ones(self) -> None:
        self.assertEqual(
            ct.split_spec("williamdemeo/site.github.io"), ("williamdemeo", "site.github.io")
        )

    def test_rejects_traversal_and_extra_components(self) -> None:
        for spec in ("org/../../outside", "org/a/b", "bare", "/leading", "org/", "org/.hidden"):
            with self.assertRaises(ct.Fatal, msg=spec):
                ct.split_spec(spec)


class ProbeLocationTest(TempDirCase):
    """Expectations are built from the repo, never from a hardcoded list."""

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        for name in ("g1", "g2"):
            (self.root / "global/skills" / name).mkdir(parents=True)
        (self.root / "projects/one/claude/skills/one-only").mkdir(parents=True)
        (self.root / "projects/one/claude/skills/g1").mkdir(parents=True)
        (self.root / "projects/two/claude/skills/two-only").mkdir(parents=True)
        write(
            self.root / "projects.toml",
            """\
            [projects.one]
            parent = "/p/one"
            [projects.two]
            parent = "/p/two"
            [projects.three]
            parent = "/p/three"
            mode = "committed"
            """,
        )
        self.manifest = ct.load_manifest(self.root / "projects.toml")

    def locations(self, targets: list[str]) -> dict[str, ct.ProbeLocation]:
        return {
            loc.label: loc for loc in ct.probe_locations(self.root, self.manifest, targets)
        }

    def test_project_expects_its_own_skills_plus_global(self) -> None:
        one = self.locations(["one"])["one"]
        self.assertEqual(one.expect_skills, ("g1", "one-only", "g1", "g2"))
        self.assertEqual(one.absent_skills, ("two-only",))
        self.assertEqual(one.cwd, Path("/p/one/main"))

    def test_global_expects_only_global_and_rejects_every_project_skill(self) -> None:
        glob = self.locations(["global"])["global"]
        self.assertEqual(glob.expect_skills, ("g1", "g2"))
        self.assertEqual(glob.absent_skills, ("one-only", "two-only"))

    def test_committed_projects_are_never_probed(self) -> None:
        self.assertNotIn("three", self.locations([]))

    def test_refuses_a_project_without_an_absolute_parent(self) -> None:
        # cwd would resolve relative to wherever probe happened to run — and
        # probe launches PAID claude sessions at that cwd. Refuse up front,
        # before any location gets a session.
        for stanza in ('[projects.p]\nmain = "main"\n', '[projects.p]\nparent = "rel/path"\n'):
            manifest = ct.load_manifest(write(self.tmp / "bad.toml", stanza))
            for targets in ([], ["p"]):
                with self.assertRaises(ct.Fatal, msg=f"{stanza!r} targets={targets}"):
                    ct.probe_locations(self.root, manifest, targets)
        self.assertEqual(
            self.locations([])["one"].foreign_markers, ("PROBE-MARKER: claude-tooling/two",)
        )

    def test_targets_filter_locations(self) -> None:
        self.assertEqual(sorted(self.locations(["two"])), ["two"])


# ---------------------------------------------------------------- end-to-end --

CT_PY = Path(__file__).resolve().parent / "ct.py"


class DeploymentFixture(TempDirCase):
    """A whole fake world: a repo copy, a fake $HOME, and a real git project.

    `ct.py` is copied in so that its repo root IS the fixture; every run gets
    $HOME pointed at the fixture too, so nothing can reach the live config.
    """

    def setUp(self) -> None:
        super().setUp()
        self.root = self.tmp / "repo"
        self.home = self.tmp / "home"
        self.parent = self.tmp / "work/demo"
        self.home.mkdir(parents=True)
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy(CT_PY, self.root / "scripts/ct.py")

        write(self.root / "global/CLAUDE.md", "PROBE-MARKER: claude-tooling/global\n")
        self.skill(self.root / "global/skills/global-skill")
        write(self.root / "projects/demo/CLAUDE.md", "PROBE-MARKER: claude-tooling/demo\n")
        self.skill(self.root / "projects/demo/claude/skills/demo-skill")
        write(self.root / "projects/demo/claude/settings.json", "{}\n")
        write(
            self.root / "projects/demo/mcp.json",
            """\
            {
              "mcpServers": {
                "demo-server": {
                  "command": "./scripts/run-server.sh",
                  "args": ["--flag", "value"],
                  "env": {"DEMO_ROOT": "${PWD}"}
                }
              }
            }
            """,
        )
        write(
            self.root / "projects.toml",
            f"""\
            [meta]
            canonical_root = "{self.root}"

            [projects.demo]
            parent = "{self.parent}"
            main   = "main"
            mode   = "symlink"
            """,
        )

    def skill(self, directory: Path) -> None:
        write(
            directory / "SKILL.md",
            f"---\nname: {directory.name}\ndescription: Use this when exercising the "
            f"{directory.name} fixture in tests.\n---\nbody\n",
        )

    def git(self, *args: str, cwd: Path | None = None) -> None:
        subprocess.run(
            ["git", "-c", "user.email=t@localhost", "-c", "user.name=t", *args],
            cwd=cwd or (self.parent / "main"),
            check=True,
            capture_output=True,
            env={**os.environ, "HOME": str(self.home)},
        )

    def make_project(self, *, track_claude: bool = False, track_mcp: bool = False) -> None:
        """A main checkout plus one linked worktree, optionally tracking members."""
        main = self.parent / "main"
        main.mkdir(parents=True)
        self.git("init", "-q", "-b", "main", ".")
        write(main / "README", "demo\n")
        tracked = ["README"]
        if track_claude:
            write(main / ".claude/settings.json", "{}\n")
            tracked.append(".claude")
        if track_mcp:
            write(main / ".mcp.json", '{"mcpServers": {}}\n')
            tracked.append(".mcp.json")
        self.git("add", *tracked)
        self.git("commit", "-qm", "initial")
        self.git("worktree", "add", "-q", "-b", "wt1", "../worktrees/wt1")

    def invoke(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(self.root / "scripts/ct.py"), *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            env={
                **os.environ,
                "HOME": str(self.home),
                "NO_COLOR": "1",
                "BACKUP_ROOT": str(self.tmp / "backups"),
                "BACKUP_STAMP": "20260809-000000",
            },
        )


class InstallEndToEndTest(DeploymentFixture):
    def setUp(self) -> None:
        super().setUp()
        self.make_project()

    def test_install_deploys_the_documented_shape(self) -> None:
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 errors", result.stdout)

        # global tier: file link + per-skill links (not a whole-dir link)
        self.assertEqual(
            os.readlink(self.home / ".claude/CLAUDE.md"), f"{self.root}/global/CLAUDE.md"
        )
        self.assertFalse((self.home / ".claude/skills").is_symlink())
        self.assertEqual(
            os.readlink(self.home / ".claude/skills/global-skill"),
            f"{self.root}/global/skills/global-skill",
        )
        # project tier: symlinked parent CLAUDE.md, REAL parent .claude
        self.assertEqual(
            os.readlink(self.parent / "CLAUDE.md"), f"{self.root}/projects/demo/CLAUDE.md"
        )
        self.assertTrue((self.parent / ".claude").is_dir())
        self.assertFalse((self.parent / ".claude").is_symlink())
        self.assertEqual(
            os.readlink(self.parent / ".claude/skills/demo-skill"),
            f"{self.root}/projects/demo/claude/skills/demo-skill",
        )
        self.assertEqual(
            os.readlink(self.parent / ".claude/settings.json"),
            f"{self.root}/projects/demo/claude/settings.json",
        )
        # every checkout root, main included, and the shared exclude line
        for checkout in ("main", "worktrees/wt1"):
            self.assertEqual(
                os.readlink(self.parent / checkout / ".claude"), f"{self.parent}/.claude"
            )
        exclude = (self.parent / "main/.git/info/exclude").read_text()
        self.assertIn("/.claude", exclude.splitlines())

    def test_check_is_green_after_install(self) -> None:
        self.invoke("install")
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("✗", result.stdout)
        self.assertIn("0 warnings, 0 errors", result.stdout)
        self.assertIn("demo worktrees: 2 linked", result.stdout)

    def test_install_is_idempotent(self) -> None:
        self.invoke("install")
        result = self.invoke("install")
        self.assertNotIn("  → ", result.stdout)  # nothing left to plan
        self.assertNotIn("  ! ", result.stdout)
        self.assertIn("0 warnings, 0 errors", result.stdout)

    def test_dry_run_changes_nothing(self) -> None:
        result = self.invoke("install", "--dry-run")
        self.assertIn("DRY RUN — nothing will be touched", result.stdout)
        self.assertFalse((self.home / ".claude").exists())
        self.assertFalse((self.parent / "CLAUDE.md").exists())
        self.assertIn(" planned,", result.stdout)

    def test_exclude_line_is_appended_only_once(self) -> None:
        self.invoke("install")
        self.invoke("install")
        exclude = (self.parent / "main/.git/info/exclude").read_text()
        self.assertEqual(exclude.count("/.claude"), 1)

    def test_new_worktrees_are_backfilled(self) -> None:
        self.invoke("install")
        self.git("worktree", "add", "-q", "-b", "wt2", "../worktrees/wt2")
        result = self.invoke("link-worktrees", "demo")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            os.readlink(self.parent / "worktrees/wt2/.claude"), f"{self.parent}/.claude"
        )

    def test_stale_worktree_registration_warns_and_is_skipped(self) -> None:
        self.invoke("install")
        shutil.rmtree(self.parent / "worktrees/wt1")
        result = self.invoke("install")
        self.assertIn(
            "path missing on disk (stale entry; consider 'git worktree prune')", result.stdout
        )
        self.assertEqual(result.returncode, 0)

    def test_orphaned_skill_link_is_reported_by_check(self) -> None:
        self.invoke("install")
        (self.root / "projects/demo/claude/skills/demo-skill").rename(
            self.root / "projects/demo/claude/skills/renamed-skill"
        )
        result = self.invoke("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("orphaned repo link demo-skill", result.stdout)

    def test_canonical_root_mismatch_warns_loudly(self) -> None:
        manifest = self.root / "projects.toml"
        manifest.write_text(
            manifest.read_text().replace(str(self.root), "/somewhere/else"), encoding="utf-8"
        )
        result = self.invoke("install", "--dry-run")
        self.assertIn(
            "not the canonical checkout (/somewhere/else) — links will point HERE",
            result.stdout,
        )

    def test_a_parentless_stanza_never_deploys_into_the_current_directory(self) -> None:
        manifest = self.root / "projects.toml"
        manifest.write_text(
            manifest.read_text().replace(f'parent = "{self.parent}"', 'parent = ""'),
            encoding="utf-8",
        )
        cwd = self.tmp / "somewhere-else"
        cwd.mkdir()
        result = self.invoke("install", cwd=cwd)
        self.assertIn("✗ parent dir missing:", result.stdout)
        self.assertEqual(sorted(p.name for p in cwd.iterdir()), [])

    def test_a_foreign_parent_claude_symlink_is_not_written_through(self) -> None:
        elsewhere = self.tmp / "someone-elses-dir"
        elsewhere.mkdir()
        (self.parent / ".claude").symlink_to(elsewhere)
        result = self.invoke("install")
        self.assertIn("!! demo/.claude — is a symlink", result.stdout)
        self.assertEqual(sorted(p.name for p in elsewhere.iterdir()), [])

    def test_a_plain_file_where_parent_claude_belongs_fails_cleanly(self) -> None:
        write(self.parent / ".claude", "not a directory\n")
        result = self.invoke("install")
        self.assertEqual(result.returncode, 1)
        self.assertIn("✗ demo/.claude — exists but is not a directory", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        self.assertEqual((self.parent / ".claude").read_text(), "not a directory\n")

    def test_a_mistyped_target_is_an_error_not_a_silent_success(self) -> None:
        for command in ("install", "check", "probe"):
            result = self.invoke(command, "demoo")
            self.assertEqual(result.returncode, 1, command)
            self.assertIn("unknown target(s): demoo", result.stdout)
            self.assertIn("known: demo global", result.stdout)

    def test_settings_local_json_in_the_repo_is_never_linked(self) -> None:
        write(self.root / "projects/demo/claude/settings.local.json", "{}\n")
        result = self.invoke("install")
        self.assertIn("that file is machine-local; not linking it", result.stdout)
        self.assertFalse((self.parent / ".claude/settings.local.json").exists())


class ForceAndBackupTest(DeploymentFixture):
    def setUp(self) -> None:
        super().setUp()
        self.make_project()
        self.live = write(self.home / ".claude/CLAUDE.md", "handwritten\n")

    def test_real_file_needs_attention_and_survives_without_force(self) -> None:
        result = self.invoke("install", "global")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.live.read_text(), "handwritten\n")
        self.assertIn("NEEDS ATTENTION (1)", result.stdout)
        self.assertIn("!! ~/.claude/CLAUDE.md — real file/dir in the way", result.stdout)

    def test_force_backs_the_original_up_before_linking(self) -> None:
        result = self.invoke("install", "--force", "global")
        self.assertEqual(result.returncode, 0, result.stdout)
        backup = self.tmp / f"backups/20260809-000000{self.live}"
        self.assertEqual(backup.read_text(), "handwritten\n")
        self.assertEqual(os.readlink(self.live), f"{self.root}/global/CLAUDE.md")
        self.assertNotIn("NEEDS ATTENTION", result.stdout)


class TrackedClaudeGuardTest(DeploymentFixture):
    """A checkout that TRACKS .claude is never touched — not even under --force."""

    def setUp(self) -> None:
        super().setUp()
        self.make_project(track_claude=True)

    def test_tracked_claude_is_skipped_under_force(self) -> None:
        result = self.invoke("install", "--force")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(".claude is TRACKED content here; skipped", result.stdout)
        for checkout in ("main", "worktrees/wt1"):
            claude = self.parent / checkout / ".claude"
            self.assertFalse(claude.is_symlink())
            self.assertEqual((claude / "settings.json").read_text(), "{}\n")

    def test_check_counts_them_as_transitional_not_broken(self) -> None:
        self.invoke("install", "--force")
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("demo worktrees: 2 with tracked .claude (transitional", result.stdout)


class McpJsonDeploymentTest(DeploymentFixture):
    """The presence-driven `.mcp.json` tier: repo copy → parent → checkout roots."""

    def setUp(self) -> None:
        super().setUp()
        self.make_project()
        self.repo_mcp = self.root / "projects/demo/mcp.json"
        self.parent_mcp = self.parent / ".mcp.json"

    def test_install_deploys_the_mcp_shape(self) -> None:
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(os.readlink(self.parent_mcp), str(self.repo_mcp))
        for checkout in ("main", "worktrees/wt1"):
            self.assertEqual(
                os.readlink(self.parent / checkout / ".mcp.json"), str(self.parent_mcp)
            )
        self.invoke("install")  # the exclude line must not accumulate
        exclude = (self.parent / "main/.git/info/exclude").read_text().splitlines()
        self.assertEqual(exclude.count("/.mcp.json"), 1)

    def test_absence_is_a_complete_no_op(self) -> None:
        # A project without projects/<p>/mcp.json gets NOTHING: no parent
        # copy, no checkout links, no exclude line — and check stays green.
        self.repo_mcp.unlink()
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.parent_mcp.is_symlink() or self.parent_mcp.exists())
        for checkout in ("main", "worktrees/wt1"):
            self.assertFalse((self.parent / checkout / ".mcp.json").exists())
        exclude = (self.parent / "main/.git/info/exclude").read_text().splitlines()
        self.assertNotIn("/.mcp.json", exclude)
        check = self.invoke("check")
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("0 warnings, 0 errors", check.stdout)

    def test_new_worktrees_get_the_mcp_link_backfilled(self) -> None:
        self.invoke("install")
        self.git("worktree", "add", "-q", "-b", "wt2", "../worktrees/wt2")
        result = self.invoke("link-worktrees", "demo")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(
            os.readlink(self.parent / "worktrees/wt2/.mcp.json"), str(self.parent_mcp)
        )

    def test_a_real_premigration_copy_survives_without_force(self) -> None:
        live = write(self.parent / "main/.mcp.json", '{"mcpServers": {"old": {}}}\n')
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("!! worktree main/.mcp.json — real file/dir in the way", result.stdout)
        self.assertEqual(live.read_text(), '{"mcpServers": {"old": {}}}\n')
        check = self.invoke("check")
        self.assertEqual(check.returncode, 0, check.stdout)
        self.assertIn("1 with a real .mcp.json (pre-migration copy", check.stdout)

    def test_force_swaps_the_real_copy_into_the_backup_tree(self) -> None:
        live = write(self.parent / "main/.mcp.json", '{"mcpServers": {"old": {}}}\n')
        result = self.invoke("install", "--force")
        self.assertEqual(result.returncode, 0, result.stdout)
        backup = self.tmp / f"backups/20260809-000000{live}"
        self.assertEqual(backup.read_text(), '{"mcpServers": {"old": {}}}\n')
        self.assertEqual(os.readlink(live), str(self.parent_mcp))
        self.assertNotIn("NEEDS ATTENTION", result.stdout)

    def test_worktrees_are_never_linked_to_an_unmanaged_parent_file(self) -> None:
        # Without --force a real parent .mcp.json survives ensure_link — and
        # checkout links to it would RESOLVE, quietly deploying content this
        # repo never saw while looking installed. They must be withheld.
        write(self.parent_mcp, '{"mcpServers": {"local": {}}}\n')
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("!! demo/.mcp.json — real file/dir in the way", result.stdout)
        self.assertIn("not linking checkout roots to it", result.stdout)
        for checkout in ("main", "worktrees/wt1"):
            live = self.parent / checkout / ".mcp.json"
            self.assertFalse(live.is_symlink() or live.exists())
        # --force adopts the parent file (backed up), then links normally.
        result = self.invoke("install", "--force")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(os.readlink(self.parent_mcp), str(self.repo_mcp))
        for checkout in ("main", "worktrees/wt1"):
            self.assertEqual(
                os.readlink(self.parent / checkout / ".mcp.json"), str(self.parent_mcp)
            )

    def test_dry_run_force_still_predicts_the_checkout_links(self) -> None:
        # A --force run adopts the parent file before the worktree pass, so
        # a --dry-run --force must plan the checkout links, not withhold them.
        write(self.parent_mcp, '{"mcpServers": {"local": {}}}\n')
        result = self.invoke("install", "--dry-run", "--force")
        self.assertIn("demo/.mcp.json — would replace real file/dir", result.stdout)
        self.assertIn("worktree main/.mcp.json — would link", result.stdout)
        self.assertNotIn("not linking checkout roots", result.stdout)

    def test_committed_mode_is_never_touched(self) -> None:
        manifest = self.root / "projects.toml"
        manifest.write_text(
            manifest.read_text().replace('mode   = "symlink"', 'mode   = "committed"'),
            encoding="utf-8",
        )
        result = self.invoke("install")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("committed-mode project", result.stdout)
        self.assertFalse(self.parent_mcp.exists())
        for checkout in ("main", "worktrees/wt1"):
            self.assertFalse((self.parent / checkout / ".mcp.json").exists())

    def test_check_flags_our_shape_when_the_repo_source_is_gone(self) -> None:
        self.invoke("install")
        self.repo_mcp.unlink()
        result = self.invoke("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("demo/.mcp.json → repo link without a source", result.stdout)
        self.assertIn(".mcp.json link without a repo source", result.stdout)

    def test_a_foreign_real_parent_mcp_json_is_not_ours_to_judge(self) -> None:
        # Unmanaged local config at the parent: check must stay silent about
        # it (only OUR deployment shape without a source is flagged).
        self.repo_mcp.unlink()
        write(self.parent_mcp, '{"mcpServers": {"local": {}}}\n')
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn(".mcp.json", result.stdout)

    def test_check_is_green_and_censuses_mcp_after_install(self) -> None:
        self.invoke("install")
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 warnings, 0 errors", result.stdout)
        self.assertIn("demo worktrees: 2 with .mcp.json linked", result.stdout)
        self.assertIn("✓ demo: /.mcp.json present in shared info/exclude", result.stdout)

    def test_list_names_the_registered_servers(self) -> None:
        result = self.invoke("list")
        self.assertEqual(result.returncode, 0)
        self.assertIn("mcp.json (servers: demo-server)", result.stdout)


class TrackedMcpJsonGuardTest(DeploymentFixture):
    """A checkout that TRACKS .mcp.json is never touched — not even under --force."""

    def setUp(self) -> None:
        super().setUp()
        self.make_project(track_mcp=True)

    def test_tracked_mcp_json_is_skipped_under_force(self) -> None:
        result = self.invoke("install", "--force")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn(".mcp.json is TRACKED content here; skipped", result.stdout)
        for checkout in ("main", "worktrees/wt1"):
            live = self.parent / checkout / ".mcp.json"
            self.assertFalse(live.is_symlink())
            self.assertEqual(live.read_text(), '{"mcpServers": {}}\n')
        # The parent copy still deploys; only the tracked checkouts are held.
        self.assertEqual(
            os.readlink(self.parent / ".mcp.json"), f"{self.root}/projects/demo/mcp.json"
        )

    def test_check_counts_them_as_guarded_not_broken(self) -> None:
        self.invoke("install", "--force")
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("demo worktrees: 2 with tracked .mcp.json", result.stdout)


class McpJsonLintTest(TempDirCase):
    """A repo mcp.json must parse, register servers, and name only live paths."""

    def build(self, mcp_text: str) -> Path:
        root = self.tmp / "repo"
        write(root / "global/CLAUDE.md", "PROBE-MARKER: claude-tooling/global\n")
        write(
            root / "projects/demo/CLAUDE.md", "PROBE-MARKER: claude-tooling/demo\n"
        )
        (root / "projects/demo/claude/skills").mkdir(parents=True, exist_ok=True)
        write(root / "projects/demo/mcp.json", mcp_text)
        return root

    def lint(self, mcp_text: str) -> tuple[ct.Reporter, str]:
        rep, buffer = capture()
        ct.run_lint(self.build(mcp_text), rep)
        return rep, buffer.getvalue()

    def test_a_valid_file_reports_its_servers(self) -> None:
        rep, out = self.lint('{"mcpServers": {"b": {}, "a": {}}}\n')
        self.assertEqual(rep.n_err, 0, out)
        self.assertIn("✓ projects/demo/mcp.json: server(s): a, b", out)

    def test_invalid_json_is_an_error(self) -> None:
        rep, out = self.lint('{"mcpServers": \n')
        self.assertEqual(rep.n_err, 1)
        self.assertIn("invalid JSON", out)

    def test_no_servers_is_an_error(self) -> None:
        # Deploying an empty registration to every checkout root would
        # silently register nothing — catch it in the repo instead.
        for text in ('{"mcpServers": {}}\n', '{"other": 1}\n', '[]\n'):
            rep, out = self.lint(text)
            self.assertEqual(rep.n_err, 1, out)
            self.assertIn("no mcpServers entries", out)

    def test_a_stale_absolute_path_is_an_error(self) -> None:
        rep, out = self.lint(
            '{"mcpServers": {"s": {"command": "/home/williamdemeo/gone-forever/run.sh"}}}\n'
        )
        self.assertEqual(rep.n_err, 1)
        self.assertIn("stale path: /home/williamdemeo/gone-forever/run.sh", out)

    def test_env_placeholders_are_not_paths(self) -> None:
        rep, out = self.lint(
            '{"mcpServers": {"s": {"command": "./run.sh", "env": {"ROOT": "${PWD}"}}}}\n'
        )
        self.assertEqual(rep.n_err, 0, out)


class McpServerNamesTest(TempDirCase):
    def test_names_are_sorted(self) -> None:
        path = write(self.tmp / "mcp.json", '{"mcpServers": {"b": {}, "a": {}}}\n')
        self.assertEqual(ct.mcp_server_names(path), ["a", "b"])

    def test_unparseable_or_shapeless_is_empty(self) -> None:
        self.assertEqual(ct.mcp_server_names(self.tmp / "absent.json"), [])
        self.assertEqual(ct.mcp_server_names(write(self.tmp / "bad.json", "{")), [])
        self.assertEqual(ct.mcp_server_names(write(self.tmp / "list.json", "[]")), [])


class GlobalSettingsTest(DeploymentFixture):
    """The global settings.json member — presence-driven, like every
    optional member."""

    def test_absent_repo_settings_deploys_nothing(self) -> None:
        result = self.invoke("install", "global")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse((self.home / ".claude/settings.json").exists())
        self.assertNotIn("~/.claude/settings.json", self.invoke("check").stdout)

    def test_present_repo_settings_links_and_check_classifies(self) -> None:
        write(self.root / "global/settings.json", '{"attribution": {"commit": ""}}\n')
        result = self.invoke("install", "global")
        self.assertEqual(result.returncode, 0, result.stdout)
        live = self.home / ".claude/settings.json"
        self.assertTrue(live.is_symlink())
        self.assertEqual(os.readlink(live), str(self.root / "global/settings.json"))
        self.assertIn("~/.claude/settings.json", self.invoke("check").stdout)

    def test_force_swaps_a_real_file_with_backup(self) -> None:
        write(self.root / "global/settings.json", '{"policy": true}\n')
        write(self.home / ".claude/settings.json", '{"machine": "local"}\n')
        result = self.invoke("install", "--force", "global")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.home / ".claude/settings.json").is_symlink())
        backups = list((self.tmp / "backups").rglob("settings.json"))
        self.assertTrue(backups, "the replaced real file must be backed up")
        self.assertEqual(backups[0].read_text(), '{"machine": "local"}\n')

    def test_a_dangling_repo_link_is_an_error_not_silence(self) -> None:
        # Presence-driven must not mean presence-blind: removing the repo
        # source after installation leaves a dangling live symlink, and
        # Claude Code then reads NO user settings at all.
        self.make_project()
        write(self.root / "global/settings.json", '{"policy": true}\n')
        self.assertEqual(self.invoke("install", "global").returncode, 0)
        (self.root / "global/settings.json").unlink()
        result = self.invoke("check")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("repo link without a source", result.stdout)

    def test_a_real_unmanaged_live_settings_is_not_flagged(self) -> None:
        # No repo source AND a real live file = unmanaged local config,
        # none of this repo's business.
        self.make_project()
        write(self.home / ".claude/settings.json", '{"machine": "local"}\n')
        result = self.invoke("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertNotIn("repo link without a source", result.stdout)


class StaleWorktreesTest(DeploymentFixture):
    """The advisory scan: verdicts and printed (never executed) removals.

    make_project()'s wt1 branches off main's tip with no commits of its
    own, so its HEAD is an ancestor of main's — the 'merged' shape.
    """

    def test_a_merged_clean_worktree_gets_a_removal_command(self) -> None:
        self.make_project()
        result = self.invoke("stale-worktrees")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("wt1 [wt1] — merged", result.stdout)
        self.assertIn(f"git -C {self.parent / 'main'} worktree remove", result.stdout)
        self.assertIn("branch -d wt1", result.stdout)
        self.assertIn("nothing was removed", result.stdout)
        self.assertTrue((self.parent / "worktrees/wt1").is_dir())  # advisory only

    def test_an_unmerged_worktree_is_active_with_no_command(self) -> None:
        self.make_project()
        wt = self.parent / "worktrees/wt1"
        write(wt / "novel.txt", "unmerged work\n")
        self.git("add", "novel.txt", cwd=wt)
        self.git("commit", "-qm", "novel", cwd=wt)
        result = self.invoke("stale-worktrees")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("wt1 [wt1] — active", result.stdout)
        self.assertNotIn("worktree remove", result.stdout)

    def test_a_dirty_stale_worktree_is_flagged_but_gets_no_command(self) -> None:
        self.make_project()
        write(self.parent / "worktrees/wt1/scratch.txt", "uncommitted\n")
        result = self.invoke("stale-worktrees")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("DIRTY", result.stdout)
        self.assertNotIn("worktree remove", result.stdout)

    def test_a_gone_upstream_is_reported(self) -> None:
        # Configure wt1 to track origin/wt1 without such a remote ref
        # existing — the state a squash-merge-then-delete leaves behind
        # after a fetch with prune.
        self.make_project()
        self.git("config", "branch.wt1.remote", "origin")
        self.git("config", "branch.wt1.merge", "refs/heads/wt1")
        result = self.invoke("stale-worktrees")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("upstream gone", result.stdout)

    def test_non_git_scan_roots_are_skipped_not_fatal(self) -> None:
        # The fixture's canonical_root (the repo copy) is not a git
        # checkout; the self-scan must degrade to a warning.
        self.make_project()
        result = self.invoke("stale-worktrees")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("not a git checkout — skipped", result.stdout)

    def test_unknown_target_is_refused(self) -> None:
        result = self.invoke("stale-worktrees", "nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown target", result.stdout)


class AddProjectTest(DeploymentFixture):
    def test_scaffolds_a_stanza_a_stub_and_a_visible_marker(self) -> None:
        result = self.invoke("add-project", "someorg/newthing", "--main", "master")
        self.assertEqual(result.returncode, 0, result.stdout)

        manifest = ct.load_manifest(self.root / "projects.toml")  # re-parses as real TOML
        project = manifest.get("newthing")
        assert project is not None
        self.assertEqual((project.parent_raw, project.main, project.mode),
                         ("~/git/someorg/newthing", "master", "symlink"))

        stub = (self.root / "projects/newthing/CLAUDE.md").read_text()
        self.assertIn("\nPROBE-MARKER: claude-tooling/newthing\n", stub)
        self.assertNotIn("<!--", stub)  # HTML comments are stripped before injection
        self.assertTrue((self.root / "projects/newthing/claude/skills/.gitkeep").is_file())

    def test_refuses_duplicates(self) -> None:
        self.assertEqual(self.invoke("add-project", "org/demo").returncode, 1)
        self.assertIn("already in", self.invoke("add-project", "org/demo").stdout)

    def test_requires_org_slash_name(self) -> None:
        result = self.invoke("add-project", "bare")
        self.assertEqual(result.returncode, 1)
        self.assertIn("expected <org>/<name>", result.stdout)

    def test_refuses_a_relative_parent(self) -> None:
        # Every mutating consumer rejects a relative parent (parent_declared),
        # so scaffolding one would only produce an unusable stanza.
        result = self.invoke("add-project", "org/newthing", "--parent", "rel/path")
        self.assertEqual(result.returncode, 1)
        self.assertIn("absolute", result.stdout)
        self.assertFalse((self.root / "projects/newthing").exists())

    def test_parent_with_toml_escape_characters_round_trips(self) -> None:
        # Raw interpolation would read a backslash as a TOML escape and a
        # quote would end the string early; json.dumps would emit the
        # non-BMP character as a UTF-16 surrogate pair, which tomllib
        # rejects, leaving the scaffold in place with an unparsable manifest.
        for i, weird in enumerate(('we"ird\\dir', "emoji 😀", "tab\there")):
            odd = str(self.tmp / weird)
            result = self.invoke("add-project", f"org/odd{i}", "--parent", odd)
            self.assertEqual(result.returncode, 0, f"{weird!r}: {result.stdout}")
            project = ct.load_manifest(self.root / "projects.toml").get(f"odd{i}")
            assert project is not None
            self.assertEqual(project.parent_raw, odd)

    def test_global_is_refused_before_any_writes(self) -> None:
        # Load-time validation alone would be too late: the scaffold would
        # already have appended a stanza that breaks every later manifest
        # parse, taking the whole tool down.
        result = self.invoke("add-project", "org/global")
        self.assertEqual(result.returncode, 1)
        self.assertIn("reserved", result.stdout)
        self.assertFalse((self.root / "projects/global").exists())
        ct.load_manifest(self.root / "projects.toml")  # still parses


class ProbeTargetTest(DeploymentFixture):
    def test_a_committed_target_is_refused_not_silently_skipped(self) -> None:
        # probe_locations filters committed projects out, so accepting the
        # target would report "total claude calls: 0" and exit 0 — a live
        # verification claiming green having verified nothing.
        with (self.root / "projects.toml").open("a", encoding="utf-8") as handle:
            handle.write('\n[projects.prod]\nparent = "/p/prod"\nmode = "committed"\n')
        result = self.invoke("probe", "prod")
        self.assertEqual(result.returncode, 1)
        self.assertIn("committed-mode", result.stdout)
        self.assertNotIn("total claude calls", result.stdout)


class ListAndLintCommandTest(DeploymentFixture):
    def test_list_reports_each_tier(self) -> None:
        result = self.invoke("list")
        self.assertEqual(result.returncode, 0)
        self.assertIn(":: global → ~/.claude", result.stdout)
        self.assertIn("global-skill", result.stdout)
        self.assertIn("demo-skill", result.stdout)

    def test_lint_subcommand_exits_zero_on_a_clean_repo(self) -> None:
        self.assertEqual(self.invoke("lint").returncode, 0)


if __name__ == "__main__":
    unittest.main()
