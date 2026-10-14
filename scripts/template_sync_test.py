# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Tests for template_sync.py.

    make template-test      # uv run scripts/template_sync_test.py

Builds throwaway template and child git repositories under a temp directory.
Git identity and config are pinned inside this process so the user's own
config (signing, default branch, ...) can't interfere, and nothing here
touches it.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import template_sync as ts  # noqa: E402

_TEST_GIT_ENV = {
    "GIT_AUTHOR_NAME": "template-sync-test",
    "GIT_AUTHOR_EMAIL": "template-sync-test@example.invalid",
    "GIT_COMMITTER_NAME": "template-sync-test",
    "GIT_COMMITTER_EMAIL": "template-sync-test@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
    # Local-path submodule URLs are refused by default (CVE-2022-39253).
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "protocol.file.allow",
    "GIT_CONFIG_VALUE_0": "always",
}
_tmp_home: tempfile.TemporaryDirectory[str]


def setUpModule() -> None:
    global _tmp_home
    _tmp_home = tempfile.TemporaryDirectory(prefix="template_sync_test-")
    os.environ.update(_TEST_GIT_ENV)
    gitconfig = Path(_tmp_home.name) / "gitconfig"
    gitconfig.write_text("")
    os.environ["GIT_CONFIG_GLOBAL"] = str(gitconfig)


def tearDownModule() -> None:
    _tmp_home.cleanup()


def sh(cwd: Path, *cmd: str) -> str:
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, "utf-8")


def commit_all(root: Path, msg: str = "c") -> str:
    sh(root, "git", "add", "-A")
    sh(root, "git", "commit", "-q", "-m", msg)
    return sh(root, "git", "rev-parse", "HEAD").strip()


def run(*argv: object) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ts.main([str(a) for a in argv])
    return code, out.getvalue(), err.getvalue()


MANIFEST = """\
manifest_format = 2
exclude = ["template.toml", "tool/**", "GUIDE.md"]

[tokens]
"demo-template" = "project"
"<HOLDER>" = "holder"

[paths]
"child/" = ""

[base]
managed = [".gitignore", ".gitmodules", "ci.yml"]
merge = ["Makefile", "child/GUIDE.md", "NOTES.md"]
seed = ["README.md", "LICENSE", "src/*.scad", "demo-template.txt", "logo.png"]

[features.docs]
description = "docs site"
managed = ["docs.yml"]
seed = ["docs/index.md"]

[features.docs_extra]
requires = ["docs"]
merge = ["docs/extra.md"]
"""

# The same template in format 1, before [paths]: without child/GUIDE.md, the only
# file that needs the mapping or a negated marker.
MANIFEST_V1 = (
    MANIFEST.replace("manifest_format = 2", "manifest_format = 1")
    .replace('[paths]\n"child/" = ""\n\n', "")
    .replace('"child/GUIDE.md", ', "")
)

# An option the template gains after a project was created from it.
LINT_FEATURE = '\n[features.lint]\ndescription = "lint config"\ndefault = false\nmanaged = ["lint.yml"]\n'

FILES = {
    ".gitignore": "out/\n",
    "ci.yml": "name: ci\n# <template-only>\nvalidate: true\n# </template-only>\nrun: make\n",
    "Makefile": "all:\n\techo demo-template\n# <template-only>\ntemplate-x:\n\techo x\n# </template-only>\n",
    "NOTES.md": "# Notes\n\nline one\n\nline two\n\nline three\n",
    "README.md": "# demo-template\n\nSee `<template-only>` for how markers work.\n",
    "LICENSE": "Copyright <HOLDER>\n",
    "src/part.scad": "cube(1);\n",
    "demo-template.txt": "{}\n",
    "docs.yml": 'docs: true\n# <template-only feature="docs_extra">\nextra: true\n# </template-only>\n',
    "docs/index.md": "# docs\n",
    "docs/extra.md": "extra\n",
    "tool/sync.py": "print('not shipped')\n",
    # The template's own guide stays here; children get child/GUIDE.md in its place.
    "GUIDE.md": "# the template's guide\n",
    "child/GUIDE.md": (
        "# guide\n"
        '<!-- <template-only feature="docs"> -->\nsee docs\n<!-- </template-only> -->\n'
        '<!-- <template-only feature="!docs"> -->\nall here\n<!-- </template-only> -->\n'
    ),
}
LOGO = b"\x89PNG\0\0binary"


class Fixture:
    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix="template_sync_test-")
        self.dir = Path(self.tmp.name)
        self.template = self.dir / "demo-template"
        self.template.mkdir()
        sh(self.template, "git", "init", "-q")
        write(self.template, "template.toml", MANIFEST)
        for rel, text in FILES.items():
            write(self.template, rel, text)
        (self.template / "logo.png").write_bytes(LOGO)
        self.head = commit_all(self.template, "template")
        self.child = self.dir / "widget"

    def cleanup(self) -> None:
        self.tmp.cleanup()

    def new(self, *extra: object) -> tuple[int, str, str]:
        return run("--template", self.template, "new", self.child, "-y", "--set", "holder=Jane", *extra)

    def check(self, *extra: object) -> tuple[int, str, str]:
        return run("--template", self.template, "check", self.child, *extra)

    def update(self, *extra: object) -> tuple[int, str, str]:
        return run("--template", self.template, "update", self.child, *extra)

    def template_commit(self, msg: str = "template") -> str:
        self.head = commit_all(self.template, msg)
        return self.head

    def child_commit(self, msg: str = "child") -> str:
        return commit_all(self.child, msg)

    def pin(self) -> str:
        config = next(rel for rel in ts.CHILD_CONFIG_PATHS if (self.child / rel).is_file())
        return tomllib.loads((self.child / config).read_text())["template"]["commit"]


class UnitTests(unittest.TestCase):
    def test_glob_to_regex(self) -> None:
        def m(pat: str, path: str) -> bool:
            return ts.glob_to_regex(pat).match(path) is not None

        self.assertTrue(m("src/*.scad", "src/a.scad"))
        self.assertFalse(m("src/*.scad", "src/x/a.scad"))
        self.assertTrue(m("**/*.md", "a.md"))
        self.assertTrue(m("**/*.md", "x/y/a.md"))
        self.assertTrue(m("tool/**", "tool/a/b"))
        self.assertFalse(m("tool/**", "tools/a"))
        self.assertTrue(m("?.txt", "a.txt"))
        self.assertFalse(m("?.txt", "ab.txt"))
        self.assertFalse(m("a.b", "aXb"))

    def test_marker_on(self) -> None:
        for line in (
            "# <template-only>",
            "// <template-only>",
            "<!-- <template-only> -->",
            "  #  <template-only>  ",
            "/* <template-only> */",
            "; <template-only>",
        ):
            self.assertEqual(ts.marker_on(line), ("open", None), line)
        self.assertEqual(ts.marker_on('# <template-only feature="docs">'), ("open", "docs"))
        self.assertEqual(ts.marker_on('# <template-only feature="!docs">'), ("open", "!docs"))
        self.assertEqual(ts.marker_on("<!-- </template-only> -->"), ("close", None))
        for line in (
            "See `<template-only>` for markers",
            "- wrap it in <template-only> markers",
            "`# <template-only>`",
            "# <template-only> extra",
            "# <template-only feature=docs>",
            '# <template-only feature="!!docs">',
            '# <template-only feature="! docs">',
        ):
            self.assertIsNone(ts.marker_on(line), line)

    def test_apply_markers(self) -> None:
        text = 'a\n# <template-only>\nb\n# </template-only>\nc\n# <template-only feature="x">\nd\n# </template-only>\n'
        self.assertEqual(ts.apply_markers(text, frozenset(), where="t")[0], "a\nc\n")
        self.assertEqual(ts.apply_markers(text, frozenset({"x"}), where="t")[0], "a\nc\nd\n")
        same, seen = ts.apply_markers(text, None, where="t")
        self.assertEqual(same, text)
        self.assertEqual(seen, {"x"})
        # A dropped block between blank lines leaves one blank line, not two;
        # at the top of a file it leaves none. A kept block keeps its spacing.
        self.assertEqual(ts.apply_markers("a\n\n# <template-only>\nb\n# </template-only>\n\nc\n", frozenset(), where="t")[0], "a\n\nc\n")
        self.assertEqual(ts.apply_markers("# <template-only>\nb\n# </template-only>\n\nc\n", frozenset(), where="t")[0], "c\n")
        self.assertEqual(ts.apply_markers("a\n# <template-only>\nb\n# </template-only>\n\nc\n", frozenset(), where="t")[0], "a\n\nc\n")
        kept = 'a\n\n# <template-only feature="x">\nb\n# </template-only>\n\nc\n'
        self.assertEqual(ts.apply_markers(kept, frozenset({"x"}), where="t")[0], "a\n\nb\n\nc\n")
        # A negated block is kept exactly when the feature is declined.
        negated = 'a\n# <template-only feature="!x">\nb\n# </template-only>\nc\n'
        self.assertEqual(ts.apply_markers(negated, frozenset(), where="t")[0], "a\nb\nc\n")
        self.assertEqual(ts.apply_markers(negated, frozenset({"x"}), where="t")[0], "a\nc\n")
        self.assertEqual(ts.apply_markers(negated, None, where="t"), (negated, {"!x"}))
        for bad in (
            "# <template-only>\nx\n",
            "x\n# </template-only>\n",
            "# <template-only>\n# <template-only>\n# </template-only>\n",
        ):
            with self.assertRaises(ts.ConfigError):
                ts.apply_markers(bad, frozenset(), where="t")

    def test_substitute(self) -> None:
        self.assertEqual(ts.substitute("abc ab", {"ab": "x", "abc": "y"}, {"x": "X", "y": "Y"}), "Y X")
        # Single pass: a replacement is never itself re-substituted.
        self.assertEqual(ts.substitute("foo", {"foo": "a", "bar": "b"}, {"a": "bar", "b": "baz"}), "bar")
        self.assertEqual(ts.substitute("plain", {}, {}), "plain")

    def test_with_feature_choices(self) -> None:
        features = {"docs": ts.Feature("docs", "docs site", False, ()), "lint": ts.Feature("lint", "", True, ())}
        # A config written when the template had no features: the placeholder comment goes.
        placeholder = f'[values]\nproject = "x"\n\n[features]\n{ts.NO_FEATURES_COMMENT}\n\n[overrides]\n"a" = "ignore"\n'
        out = ts.with_feature_choices(placeholder, features, {"docs": False})
        self.assertNotIn(ts.NO_FEATURES_COMMENT, out)
        self.assertIn("# docs site\ndocs = false\n\n[overrides]\n", out)
        self.assertEqual(tomllib.loads(out), {"values": {"project": "x"}, "features": {"docs": False}, "overrides": {"a": "ignore"}})
        # Appended after existing choices, or in a new table if there is none.
        out = ts.with_feature_choices("[features]\ndocs = true\n", features, {"lint": True})
        self.assertEqual(out, "[features]\ndocs = true\nlint = true\n")
        out = ts.with_feature_choices('[values]\nproject = "x"\n', features, {"docs": True})
        self.assertEqual(tomllib.loads(out)["features"], {"docs": True})

    def test_decide_managed(self) -> None:
        def d(base: bytes | None, theirs: bytes | None, mine: bytes | None) -> ts.FileResult:
            return ts.decide(ts.FileResult("p", "p", "managed"), base, theirs, mine, ("a", "b", "c"))

        self.assertEqual(d(b"1", b"1", b"1").status, "ok")
        r = d(b"1", b"2", b"1")
        self.assertEqual((r.status, r.change, r.content), ("update", True, b"2"))
        r = d(b"1", b"1", b"9")
        self.assertEqual((r.status, r.error, r.content), ("drift", True, b"1"))
        self.assertIn("also changed", d(b"1", b"2", b"9").note)
        self.assertEqual(d(None, b"2", None).status, "new")
        r = d(b"1", b"2", None)
        self.assertEqual((r.status, r.error, r.content), ("drift", True, b"2"))
        self.assertEqual(d(b"1", None, b"1").status, "delete")
        self.assertEqual(d(b"1", None, b"9").status, "drift")
        self.assertEqual(d(b"1", None, None).status, "ok")

    def test_decide_merge(self) -> None:
        def d(base: bytes | None, theirs: bytes | None, mine: bytes | None) -> ts.FileResult:
            return ts.decide(ts.FileResult("p", "p", "merge"), base, theirs, mine, ("a", "b", "c"))

        self.assertEqual(d(b"1\n", b"1\n", b"9\n").status, "local")
        self.assertEqual(d(b"1\n", b"2\n", b"1\n").status, "update")
        self.assertEqual(d(b"1\n", b"2\n", b"2\n").status, "ok")  # child already took it
        self.assertEqual(d(b"1\n", None, b"9\n").status, "removed-upstream")
        self.assertEqual(d(b"1\n", b"2\n", None).status, "local")
        self.assertEqual(d(None, b"2\n", b"9\n").status, "local")
        base = b"a\n\nb\n\nc\n"
        r = d(base, b"a\n\nb\n\nC\n", b"A\n\nb\n\nc\n")
        self.assertEqual((r.status, r.content), ("merged", b"A\n\nb\n\nC\n"))
        r = d(base, b"a\n\nB\n\nc\n", b"a\n\nX\n\nc\n")
        self.assertEqual((r.status, r.error), ("conflict", True))
        assert r.content is not None
        self.assertIn(b"<<<<<<< a", r.content)
        r = d(b"1\n", b"2\n", b"<<<<<<< a\n1\n=======\n2\n>>>>>>> c\n")
        self.assertEqual(r.status, "markers")

    def test_decide_seed(self) -> None:
        def d(base: bytes | None, theirs: bytes | None, mine: bytes | None) -> ts.FileResult:
            return ts.decide(ts.FileResult("p", "p", "seed"), base, theirs, mine, ("a", "b", "c"))

        self.assertEqual(d(None, b"1", None).status, "seed-available")
        self.assertEqual(d(b"1", b"2", None).status, "ok")
        self.assertEqual(d(b"1", b"2", b"9").status, "ok")


class ManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)

    def validate(self) -> tuple[int, str, str]:
        return run("--template", self.fx.template, "validate")

    def set_manifest(self, text: str) -> None:
        write(self.fx.template, "template.toml", text)
        self.fx.template_commit("manifest")

    def assert_rejected(self, fragment: str) -> None:
        code, _out, err = self.validate()
        self.assertEqual(code, 2, err)
        self.assertIn(fragment, err)

    def test_validate_ok(self) -> None:
        code, out, err = self.validate()
        self.assertEqual(code, 0, err)
        self.assertIn("classified", out)
        self.assertIn("features: docs (default on), docs_extra (default on)", out)

    def test_unclassified_file(self) -> None:
        write(self.fx.template, "stray.txt", "x\n")
        self.fx.template_commit()
        self.assert_rejected("stray.txt: not classified")

    def test_ambiguous_file(self) -> None:
        self.set_manifest(MANIFEST.replace('"ci.yml"]', '"ci.yml", "*.yml"]'))
        self.assert_rejected("several rules")

    def test_merge_binary(self) -> None:
        self.set_manifest(MANIFEST.replace(', "logo.png"]', "]").replace('"NOTES.md"]', '"NOTES.md", "logo.png"]'))
        self.assert_rejected("binary files cannot be `merge`")

    def test_unbalanced_marker(self) -> None:
        write(self.fx.template, "ci.yml", "# <template-only>\nx\n")
        self.fx.template_commit()
        self.assert_rejected("never closed")

    def test_undeclared_feature_marker(self) -> None:
        for tag in ("nope", "!nope"):
            with self.subTest(tag=tag):
                write(self.fx.template, "ci.yml", f'# <template-only feature="{tag}">\nx\n# </template-only>\n')
                self.fx.template_commit()
                self.assert_rejected('feature="nope"> names an undeclared feature')

    def test_path_clash(self) -> None:
        # Ship the template's own GUIDE.md too, and it collides with child/GUIDE.md.
        self.set_manifest(MANIFEST.replace(', "GUIDE.md"]', "]").replace('"ci.yml"]', '"ci.yml", "GUIDE.md"]'))
        self.assert_rejected("GUIDE.md: shipped from several template files: GUIDE.md, child/GUIDE.md")

    def test_bad_paths(self) -> None:
        for entry in ('"child" = ""', '"../child/" = ""', '"./child/" = ""', '"child/" = "/abs/"', '"child/" = 1'):
            with self.subTest(entry=entry):
                self.set_manifest(MANIFEST.replace('"child/" = ""', entry))
                self.assert_rejected("[paths]")

    def test_stale_paths_warns(self) -> None:
        self.set_manifest(MANIFEST.replace('"child/" = ""', '"child/" = ""\n"nowhere/" = "x/"'))
        code, out, err = self.validate()
        self.assertEqual(code, 0, err)
        self.assertIn("[paths] 'nowhere/' matches no shipped file", out)

    def test_requires_unknown(self) -> None:
        self.set_manifest(MANIFEST.replace('requires = ["docs"]', 'requires = ["nope"]'))
        self.assert_rejected("unknown feature")

    def test_requires_cycle(self) -> None:
        self.set_manifest(MANIFEST.replace('description = "docs site"\n', 'description = "docs site"\nrequires = ["docs_extra"]\n'))
        self.assert_rejected("cycle")

    def test_unknown_key(self) -> None:
        self.set_manifest(MANIFEST + "\n[bogus]\nx = 1\n")
        self.assert_rejected("unknown key")

    def test_bad_format(self) -> None:
        for value, message in (
            ("3", "manifest_format = 3, but this tool reads formats up to 2"),
            ("0", "positive integer"),
            ("true", "positive integer"),
            ('"2"', "positive integer"),
        ):
            with self.subTest(value=value):
                self.set_manifest(MANIFEST.replace("manifest_format = 2", f"manifest_format = {value}"))
                self.assert_rejected(message)

    def test_newer_format_is_refused_before_its_keys(self) -> None:
        # A format-3 manifest with a key this tool has never heard of: the number is what's reported.
        self.set_manifest(MANIFEST.replace("manifest_format = 2", "manifest_format = 3") + "\n[future]\nx = 1\n")
        code, _out, err = self.validate()
        self.assertEqual(code, 2, err)
        self.assertIn("reads formats up to 2", err)
        self.assertNotIn("unknown key", err)

    def test_format_1_manifest(self) -> None:
        write(self.fx.template, "template.toml", MANIFEST_V1)
        sh(self.fx.template, "git", "rm", "-q", "child/GUIDE.md")
        self.fx.template_commit("format 1")
        code, _out, err = self.validate()
        self.assertEqual(code, 0, err)
        # What format 2 added is refused under format 1.
        self.set_manifest(MANIFEST_V1 + '\n[paths]\n"child/" = ""\n')
        self.assert_rejected("[paths] needs manifest_format = 2")
        self.set_manifest(MANIFEST_V1)
        write(self.fx.template, "ci.yml", '# <template-only feature="!docs">\nx\n# </template-only>\n')
        self.fx.template_commit()
        self.assert_rejected('ci.yml: negated markers (feature="!name") need manifest_format = 2')

    def test_stale_pattern_warns(self) -> None:
        self.set_manifest(MANIFEST.replace('"ci.yml"]', '"ci.yml", "nothing.txt"]'))
        code, out, err = self.validate()
        self.assertEqual(code, 0, err)
        self.assertIn("'nothing.txt' matches no tracked file", out)

    def test_check_on_template_itself(self) -> None:
        code, _out, err = run("--template", self.fx.template, "check", self.fx.template)
        self.assertEqual(code, 2)
        self.assertIn("template itself", err)


class SyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fx = Fixture()
        self.addCleanup(self.fx.cleanup)
        code, _out, err = self.fx.new()
        self.assertEqual(code, 0, err)
        self.fx.child_commit("initial")

    def read(self, rel: str) -> str:
        return (self.fx.child / rel).read_text("utf-8")

    def exists(self, rel: str) -> bool:
        return (self.fx.child / rel).exists()

    def edit_child(self, rel: str, text: str, *, commit: bool = True) -> None:
        write(self.fx.child, rel, text)
        if commit:
            self.fx.child_commit()

    def edit_template(self, rel: str, text: str) -> None:
        write(self.fx.template, rel, text)
        self.fx.template_commit()

    def statuses(self, out: str) -> dict[str, str]:
        result = {}
        for line in out.splitlines():
            parts = line.split()
            if line.startswith("  ") and len(parts) >= 2 and not line.startswith("  note:") and not parts[0].startswith("submodule"):
                result[parts[1]] = parts[0]
        return result

    # -- new ---------------------------------------------------------------

    def test_new_layout(self) -> None:
        for rel in (".gitignore", "ci.yml", "Makefile", "NOTES.md", "README.md", "LICENSE", "src/part.scad",
                    "widget.txt", "docs.yml", "docs/index.md", "docs/extra.md", "logo.png", ".template.toml",
                    "GUIDE.md"):
            self.assertTrue(self.exists(rel), rel)
        for rel in ("template.toml", "tool/sync.py", "tool", "demo-template.txt", "child"):
            self.assertFalse(self.exists(rel), rel)
        self.assertEqual(self.read("GUIDE.md"), "# guide\nsee docs\n")
        self.assertEqual(self.read("ci.yml"), "name: ci\nrun: make\n")
        self.assertEqual(self.read("Makefile"), "all:\n\techo widget\n")
        self.assertEqual(self.read("README.md"), "# widget\n\nSee `<template-only>` for how markers work.\n")
        self.assertEqual(self.read("LICENSE"), "Copyright Jane\n")
        self.assertEqual(self.read("docs.yml"), "docs: true\nextra: true\n")
        self.assertEqual((self.fx.child / "logo.png").read_bytes(), LOGO)
        cfg = tomllib.loads(self.read(".template.toml"))
        self.assertEqual(cfg["template"]["commit"], self.fx.head)
        self.assertEqual(cfg["values"], {"project": "widget", "holder": "Jane"})
        self.assertEqual(cfg["features"], {"docs": True, "docs_extra": True})
        self.assertEqual(sh(self.fx.child, "git", "rev-parse", "--abbrev-ref", "HEAD").strip(), "main")

    def test_new_stages_everything(self) -> None:
        fx = Fixture()
        self.addCleanup(fx.cleanup)
        code, out, err = fx.new()
        self.assertEqual(code, 0, err)
        self.assertIn("nothing is committed", out)
        staged = sh(fx.child, "git", "diff", "--cached", "--name-only").split()
        self.assertIn(".template.toml", staged)
        self.assertIn("widget.txt", staged)

    def test_new_refuses_nonempty_target(self) -> None:
        code, _out, err = self.fx.new()
        self.assertEqual(code, 2)
        self.assertIn("not an empty directory", err)

    def test_new_feature_off_and_defaults(self) -> None:
        other = self.fx.dir / "other"
        code, out, err = run("--template", self.fx.template, "new", other, "-y", "--feature", "docs=false")
        self.assertEqual(code, 0, err)
        self.assertIn("feature docs_extra turned off", out)
        for rel in ("docs.yml", "docs/index.md", "docs/extra.md"):
            self.assertFalse((other / rel).exists(), rel)
        self.assertEqual((other / "GUIDE.md").read_text(), "# guide\nall here\n")
        cfg = tomllib.loads((other / ".template.toml").read_text())
        self.assertEqual(cfg["features"], {"docs": False, "docs_extra": False})
        # Unset values: project defaults to the directory name, anything else to the placeholder.
        self.assertEqual(cfg["values"], {"project": "other", "holder": "<HOLDER>"})
        self.assertEqual((other / "LICENSE").read_text(), "Copyright <HOLDER>\n")

    def test_new_prompts_for_features(self) -> None:
        other = self.fx.dir / "other"
        tty = mock.Mock(isatty=lambda: True)
        # docs: Enter takes the default (on); docs_extra: an unclear answer is asked again.
        with mock.patch("sys.stdin", tty), mock.patch("builtins.input", side_effect=["", "maybe", "n"]) as ask:
            code, _out, err = run("--template", self.fx.template, "new", other, "--set", "project=other", "--set", "holder=Jane")
        self.assertEqual(code, 0, err)
        self.assertEqual(ask.call_count, 3)
        self.assertTrue(ask.call_args_list[0].args[0].startswith("docs (docs site) [Y/n]"))
        cfg = tomllib.loads((other / ".template.toml").read_text())
        self.assertEqual(cfg["features"], {"docs": True, "docs_extra": False})

    def test_new_refuses_dirty_template(self) -> None:
        write(self.fx.template, "ci.yml", "changed\n")
        other = self.fx.dir / "other"
        code, _out, err = run("--template", self.fx.template, "new", other, "-y")
        self.assertEqual(code, 2)
        self.assertIn("uncommitted changes", err)

    # -- check / update ------------------------------------------------------

    def test_check_clean(self) -> None:
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertIn("child pin is current", out)
        self.assertIn("0 pending change(s); 0 error(s)", out)

    def test_update_managed_and_merge(self) -> None:
        self.edit_template(".gitignore", "out/\n*.stl\n")
        self.edit_template("NOTES.md", "# Notes\n\nline one\n\nline two\n\nline 3\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out), {".gitignore": "update", "NOTES.md": "update"})
        self.assertIn("2 commit(s) behind", out)
        self.assertEqual(self.fx.check("--strict")[0], 1)

        code, out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read(".gitignore"), "out/\n*.stl\n")
        self.assertIn("line 3", self.read("NOTES.md"))
        self.assertEqual(self.fx.pin(), self.fx.head)
        self.assertIn(f"pin -> {self.fx.head[:7]}"[4:], out)
        self.fx.child_commit()
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertIn("child pin is current", out)

    def add_lint_feature(self) -> None:
        write(self.fx.template, "template.toml", MANIFEST + LINT_FEATURE)
        write(self.fx.template, "lint.yml", "lint: true\n")
        self.fx.template_commit("add lint")

    def test_update_records_new_feature(self) -> None:
        self.add_lint_feature()
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertIn("[features] lint is unset, so its default (off) applies", out)
        code, out, err = self.fx.update()  # not a terminal: takes the default
        self.assertEqual(code, 0, err)
        self.assertIn("recorded in .template.toml: lint = false", out)
        self.assertIs(tomllib.loads(self.read(".template.toml"))["features"]["lint"], False)
        self.assertFalse(self.exists("lint.yml"))
        self.fx.child_commit()
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertNotIn("lint is unset", out)

    def test_update_asks_about_new_feature(self) -> None:
        self.add_lint_feature()
        tty = mock.Mock(isatty=lambda: True)
        with mock.patch("sys.stdin", tty), mock.patch("builtins.input", side_effect=["y"]) as ask:
            code, out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertEqual(ask.call_count, 1)
        self.assertTrue(ask.call_args.args[0].startswith("lint (lint config) [y/N]"))
        self.assertIn("hasn't chosen yet", out)
        self.assertIs(tomllib.loads(self.read(".template.toml"))["features"]["lint"], True)
        self.assertEqual(self.read("lint.yml"), "lint: true\n")

    def test_managed_drift_is_restored(self) -> None:
        self.edit_child(".gitignore", "out/\nmine/\n")
        code, out, _err = self.fx.check()
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(out)[".gitignore"], "drift")
        code, _out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read(".gitignore"), "out/\n")

    def test_merge_keeps_local_edit(self) -> None:
        self.edit_child("NOTES.md", "# Notes\n\nline ONE\n\nline two\n\nline three\n")
        self.edit_template("NOTES.md", "# Notes\n\nline one\n\nline two\n\nline THREE\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out)["NOTES.md"], "merged")
        code, _out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("NOTES.md"), "# Notes\n\nline ONE\n\nline two\n\nline THREE\n")

    def test_merge_local_only_is_not_drift(self) -> None:
        self.edit_child("NOTES.md", "# Notes\n\nmine\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out)["NOTES.md"], "local")
        self.fx.update()
        self.assertEqual(self.read("NOTES.md"), "# Notes\n\nmine\n")

    def test_format_bump_keeps_reading_the_pin(self) -> None:
        # A child pinned under format 1. The bump to 2 lands with ci.yml's removal, and only
        # the manifest at the pin knows ci.yml was managed -- so that manifest must stay readable.
        fx = Fixture()
        self.addCleanup(fx.cleanup)
        write(fx.template, "template.toml", MANIFEST_V1)
        sh(fx.template, "git", "rm", "-q", "child/GUIDE.md")
        fx.template_commit("format 1")
        code, _out, err = fx.new()
        self.assertEqual(code, 0, err)
        fx.child_commit()
        write(fx.template, "template.toml", MANIFEST.replace(', "ci.yml"]', "]"))
        write(fx.template, "child/GUIDE.md", FILES["child/GUIDE.md"])
        sh(fx.template, "git", "rm", "-q", "ci.yml")
        fx.template_commit("format 2")
        code, out, err = fx.check()
        self.assertEqual(code, 0, err)
        self.assertNotIn("no readable", out)
        self.assertEqual(self.statuses(out), {"ci.yml": "delete", "child/GUIDE.md": "new"})

    def test_mapped_path(self) -> None:
        self.edit_template("GUIDE.md", "# the template's guide, reworded\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out), {})
        self.edit_template("child/GUIDE.md", FILES["child/GUIDE.md"].replace("# guide", "# Guide"))
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out), {"child/GUIDE.md": "update"})
        self.assertIn("child/GUIDE.md -> GUIDE.md", out)
        code, _out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("GUIDE.md"), "# Guide\nsee docs\n")
        self.assertFalse(self.exists("child"))

    def test_template_only_edits_are_invisible(self) -> None:
        self.edit_template("Makefile", "all:\n\techo demo-template\n# <template-only>\ntemplate-y:\n\techo y\n# </template-only>\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertNotIn("Makefile", self.statuses(out))

    def test_conflict_cycle(self) -> None:
        self.edit_child("NOTES.md", "# Notes\n\nline one\n\nchild two\n\nline three\n")
        self.edit_template("NOTES.md", "# Notes\n\nline one\n\ntemplate two\n\nline three\n")
        old_pin = self.fx.pin()
        code, out, _err = self.fx.update()
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(out)["NOTES.md"], "conflict")
        notes = self.read("NOTES.md")
        self.assertIn("<<<<<<< yours", notes)
        self.assertIn(f"||||||| template@{old_pin[:7]}", notes)  # --diff3: the base is labelled with the old pin
        self.assertIn(f">>>>>>> template@{self.fx.head[:7]}", notes)
        self.assertEqual(self.fx.pin(), self.fx.head)
        self.fx.child_commit("conflicted")
        code, out, _err = self.fx.check()
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(out)["NOTES.md"], "markers")
        code, _out, err = self.fx.update()
        self.assertEqual(code, 2)
        self.assertIn("resolve the conflict markers", err)
        self.edit_child("NOTES.md", "# Notes\n\nline one\n\nboth two\n\nline three\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out)["NOTES.md"], "local")

    def test_new_and_seed_files(self) -> None:
        write(self.fx.template, "template.toml", MANIFEST.replace('"ci.yml"]', '"ci.yml", "extra.yml"]'))
        write(self.fx.template, "extra.yml", "extra: 1\n")
        write(self.fx.template, "src/other.scad", "sphere(1);\n")
        self.fx.template_commit()
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out), {"extra.yml": "new", "src/other.scad": "seed-available"})
        self.assertEqual(self.fx.check("--strict")[0], 1)
        code, _out, err = self.fx.update("--seed")
        self.assertEqual(code, 0, err)
        self.assertEqual(self.read("extra.yml"), "extra: 1\n")
        self.assertEqual(self.read("src/other.scad"), "sphere(1);\n")

    def test_seed_offer_closes_with_the_pin(self) -> None:
        self.edit_template("src/other.scad", "sphere(1);\n")
        code, _out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertFalse(self.exists("src/other.scad"))
        self.fx.child_commit()
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertNotIn("src/other.scad", out)

    def test_delete_upstream(self) -> None:
        write(self.fx.template, "template.toml", MANIFEST.replace(', "ci.yml"]', "]"))
        sh(self.fx.template, "git", "rm", "-q", "ci.yml")
        self.fx.template_commit("drop ci")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out)["ci.yml"], "delete")
        code, _out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertFalse(self.exists("ci.yml"))

    def test_delete_upstream_but_edited_locally(self) -> None:
        self.edit_child("ci.yml", "name: ci\nrun: make mine\n")
        write(self.fx.template, "template.toml", MANIFEST.replace(', "ci.yml"]', "]"))
        sh(self.fx.template, "git", "rm", "-q", "ci.yml")
        self.fx.template_commit("drop ci")
        code, out, _err = self.fx.check()
        self.assertEqual(code, 1)
        self.assertEqual(self.statuses(out)["ci.yml"], "drift")
        self.fx.update()
        self.assertTrue(self.exists("ci.yml"))

    def test_overrides(self) -> None:
        cfg = self.read(".template.toml") + '".gitignore" = "merge"\n"ci.yml" = "ignore"\n'
        self.edit_child(".template.toml", cfg, commit=False)
        self.edit_child(".gitignore", "out/\nmine/\n", commit=False)
        self.edit_child("ci.yml", "whatever\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.statuses(out), {".gitignore": "local", "ci.yml": "ignored"})

    def test_feature_requires_propagates(self) -> None:
        cfg = self.read(".template.toml").replace("docs = true", "docs = false")
        self.edit_child(".template.toml", cfg)
        code, out, err = self.fx.check("--all")
        self.assertEqual(code, 0, err)
        self.assertIn("note: feature docs_extra turned off: it requires docs", out)
        for rel in ("docs.yml", "docs/index.md", "docs/extra.md"):
            self.assertNotIn(rel, self.statuses(out))

    def test_update_refuses_dirty_child(self) -> None:
        self.edit_child("NOTES.md", "dirty\n", commit=False)
        code, _out, err = self.fx.update()
        self.assertEqual(code, 2)
        self.assertIn("uncommitted changes", err)
        code, _out, err = self.fx.update("--force")
        self.assertEqual(code, 0, err)

    def test_update_refuses_dirty_template_but_check_warns(self) -> None:
        write(self.fx.template, "ci.yml", "changed\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)  # the working-tree change reads as a pending update
        self.assertEqual(self.statuses(out)["ci.yml"], "update")
        self.assertIn("warning: template has uncommitted changes", err)
        code, _out, err = self.fx.update()
        self.assertEqual(code, 2)
        self.assertIn("uncommitted changes", err)

    def test_check_without_config(self) -> None:
        (self.fx.child / ".template.toml").unlink()
        code, _out, err = self.fx.check()
        self.assertEqual(code, 2)
        self.assertIn("no .template.toml or .local/.template.toml", err)
        self.assertIn("[template]", err)
        self.assertIn("project = ", err)

    def test_config_in_local(self) -> None:
        # Untracked in .local/, so the project's history holds nothing of the sync's.
        write(self.fx.child, ".git/info/exclude", ".local/\n")  # the fixture's .gitignore doesn't
        sh(self.fx.child, "git", "rm", "-q", "--cached", ".template.toml")
        (self.fx.child / ".local").mkdir()
        (self.fx.child / ".template.toml").rename(self.fx.child / ".local/.template.toml")
        self.fx.child_commit("keep the config local")
        self.add_lint_feature()
        self.edit_template(".gitignore", "out/\n*.stl\n")
        code, out, err = self.fx.update()
        self.assertEqual(code, 0, err)
        self.assertIn("recorded in .local/.template.toml: lint = false", out)
        self.assertIs(tomllib.loads(self.read(".local/.template.toml"))["features"]["lint"], False)
        self.assertEqual(self.fx.pin(), self.fx.head)
        self.assertFalse(self.exists(".template.toml"))
        self.assertEqual(sh(self.fx.child, "git", "status", "--porcelain").split(), ["M", ".gitignore"])

    def test_root_config_wins_over_local(self) -> None:
        write(self.fx.child, ".local/.template.toml", "not toml [\n")
        code, out, err = self.fx.check()
        self.assertEqual(code, 0, err)
        self.assertIn("note: .local/.template.toml is not read: .template.toml takes precedence", out)

    def test_check_rejects_bad_config(self) -> None:
        self.edit_child(".template.toml", self.read(".template.toml").replace("holder = ", "holdr = "))
        code, _out, err = self.fx.check()
        self.assertEqual(code, 2)
        self.assertIn("missing holder", err)

    def test_submodule(self) -> None:
        lib = self.fx.dir / "lib"
        lib.mkdir()
        sh(lib, "git", "init", "-q")
        write(lib, "lib.scad", "x\n")
        sha = commit_all(lib, "lib")
        sh(self.fx.template, "git", "submodule", "--quiet", "add", str(lib), "vendor/lib")
        self.fx.template_commit("submodule")
        other = self.fx.dir / "other"
        code, out, err = run("--template", self.fx.template, "new", other, "-y")
        self.assertEqual(code, 0, err)
        self.assertIn(f"submodule vendor/lib @ {sha[:7]}", out)
        self.assertEqual((other / ".gitmodules").read_text(), (self.fx.template / ".gitmodules").read_text())
        self.assertTrue((other / "vendor/lib/lib.scad").exists())
        index = sh(other, "git", "ls-files", "-s", "vendor/lib")
        self.assertIn("160000", index)
        self.assertIn(sha, index)
        # Nothing committed yet: the submodule is staged, not missing.
        code, out, err = run("--template", self.fx.template, "check", other, "--all")
        self.assertEqual(code, 0, err)
        self.assertIn(f"submodule vendor/lib: in sync at {sha[:7]}", out)
        commit_all(other, "initial")
        code, out, err = run("--template", self.fx.template, "check", other, "--all")
        self.assertEqual(code, 0, err)
        self.assertIn(f"submodule vendor/lib: in sync at {sha[:7]}", out)
        # Created without submodules, it really is missing, and check says how to add it.
        bare = self.fx.dir / "bare"
        code, _out, err = run("--template", self.fx.template, "new", bare, "-y", "--no-submodules")
        self.assertEqual(code, 0, err)
        code, out, err = run("--template", self.fx.template, "check", bare)
        self.assertEqual(code, 0, err)
        self.assertIn("submodule vendor/lib: not in the child (git submodule add ", out)


class RealTemplateTests(unittest.TestCase):
    ROOT = Path(__file__).resolve().parent.parent

    @unittest.skipUnless((ROOT / ts.MANIFEST_NAME).is_file(), "not inside a template checkout")
    def test_manifest_classifies_every_tracked_file(self) -> None:
        code, _out, err = run("--template", self.ROOT, "validate")
        self.assertEqual(code, 0, err)

    @unittest.skipUnless((ROOT / ts.MANIFEST_NAME).is_file(), "not inside a template checkout")
    def test_new_with_and_without_docs(self) -> None:
        tmp = tempfile.TemporaryDirectory(prefix="template_sync_test-")
        self.addCleanup(tmp.cleanup)
        pages = {"docs/index.md", "docs/getting-started.md", "docs/development.md"}
        for docs in ("true", "false"):
            with self.subTest(docs=docs):
                child = Path(tmp.name) / f"docs-{docs}"
                code, _out, err = run(
                    "--template", self.ROOT, "new", child, "-y", "--force", "--no-submodules", "--feature", f"docs={docs}"
                )
                self.assertEqual(code, 0, err)
                shipped = set(sh(child, "git", "ls-files").split())
                has_docs = docs == "true"
                self.assertEqual({p for p in shipped if p.startswith("docs/") and p.endswith(".md")}, pages if has_docs else set())
                self.assertEqual("mkdocs.yml" in shipped, has_docs)
                self.assertEqual("docs/index.md" in (child / "README.md").read_text(), has_docs)
                self.assertFalse([p for p in shipped if p.startswith("child/")])
                for rel in sorted(shipped):
                    data = (child / rel).read_bytes()
                    if not ts.is_binary(data):
                        for n, line in enumerate(data.decode("utf-8").split("\n"), 1):
                            self.assertIsNone(ts.marker_on(line), f"leftover marker at {rel}:{n}")


if __name__ == "__main__":
    unittest.main()
