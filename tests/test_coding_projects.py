"""Tests for core.coding_projects: project resolution and path containment.

All tests are hermetic: they build temporary roots and patch the module-level
APPROVED_ROOTS so the real user profile is never consulted.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import coding_projects as cp


class LooksLikeProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pyproject_marker(self):
        d = self.root / "with_pyproject"
        d.mkdir()
        (d / "pyproject.toml").write_text("[project]\nname='x'\n")
        self.assertTrue(cp.looks_like_project(d))

    def test_only_python_file(self):
        d = self.root / "only_py"
        d.mkdir()
        (d / "script.py").write_text("print('hi')\n")
        self.assertTrue(cp.looks_like_project(d))

    def test_csproj_glob_marker(self):
        d = self.root / "cs"
        d.mkdir()
        (d / "App.csproj").write_text("<Project/>\n")
        self.assertTrue(cp.looks_like_project(d))

    def test_empty_dir_is_not_project(self):
        d = self.root / "empty"
        d.mkdir()
        self.assertFalse(cp.looks_like_project(d))

    def test_nonexistent_path_is_not_project(self):
        self.assertFalse(cp.looks_like_project(self.root / "does_not_exist"))


class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "root"
        self.root.mkdir()
        self.outside = self.base / "outside"
        self.outside.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_contains_relative_inside(self):
        self.assertTrue(cp.contains(self.root, "sub/file.py"))

    def test_contains_relative_escape(self):
        self.assertFalse(cp.contains(self.root, "../outside.py"))

    def test_contains_absolute_outside(self):
        target = self.outside / "evil.py"
        target.write_text("pass\n")
        self.assertFalse(cp.contains(self.root, target))
        self.assertFalse(cp.contains(self.root, str(target)))

    def test_contains_absolute_inside(self):
        target = self.root / "sub" / "file.py"
        self.assertTrue(cp.contains(self.root, target))
        self.assertTrue(cp.contains(self.root, str(target)))

    def test_is_within_direct(self):
        self.assertTrue(cp.is_within(self.root / "sub", self.root))
        self.assertTrue(cp.is_within(self.root, self.root))
        self.assertFalse(cp.is_within(self.outside, self.root))
        self.assertFalse(cp.is_within(self.base, self.root))


class ResolveProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        self.project = self.root / "portfolio"
        self.project.mkdir()
        (self.project / "pyproject.toml").write_text("[project]\nname='portfolio'\n")
        self._patcher = mock.patch.object(cp, "APPROVED_ROOTS", (self.root,))
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        self.tmp.cleanup()

    def test_patch_affects_approved_roots(self):
        roots = cp.approved_roots()
        self.assertIn(self.root.resolve(), roots)
        self.assertEqual(cp.find_named_project("portfolio"), [self.project])

    def test_resolve_by_name(self):
        resolved = cp.resolve_project("portfolio")
        self.assertEqual(resolved, self.project.resolve())
        self.assertTrue(resolved.is_absolute())

    def test_resolve_by_name_case_insensitive(self):
        self.assertEqual(cp.resolve_project("PORTFOLIO"), self.project.resolve())

    def test_resolve_by_absolute_path(self):
        resolved = cp.resolve_project(str(self.project))
        self.assertEqual(resolved, self.project.resolve())

    def test_resolved_project_is_contained(self):
        for requested in ("portfolio", str(self.project)):
            resolved = cp.resolve_project(requested)
            roots = cp.approved_roots()
            self.assertTrue(
                any(cp.is_within(resolved, root) for root in roots),
                f"{requested!r} resolved to {resolved}, outside {roots}",
            )

    def test_unknown_name_raises(self):
        with self.assertRaises(cp.ProjectError):
            cp.resolve_project("no_such_project_anywhere")

    def test_blank_string_raises(self):
        for blank in ("", "   ", "\t", '""', "''"):
            with self.assertRaises(cp.ProjectError):
                cp.resolve_project(blank)

    def test_absolute_outside_raises(self):
        outside = Path(self.tmp.name) / "outside"
        outside.mkdir()
        (outside / "pyproject.toml").write_text("[project]\n")
        with self.assertRaises(cp.ProjectError):
            cp.resolve_project(str(outside))

    def test_absolute_inside_without_project_markers_raises(self):
        empty = self.root / "empty_project"
        empty.mkdir()
        with self.assertRaises(cp.ProjectError):
            cp.resolve_project(str(empty))

    def test_nonexistent_absolute_raises(self):
        with self.assertRaises(cp.ProjectError):
            cp.resolve_project(str(self.root / "ghost"))

    def test_not_found_message_is_speakable(self):
        try:
            cp.resolve_project("definitely_missing_project")
        except cp.ProjectError as exc:
            message = str(exc)
        else:
            self.fail("ProjectError was not raised")
        self.assertTrue(message)
        self.assertTrue(message[0].isupper(), message)
        self.assertNotIn("Traceback", message)
        self.assertNotIn("Error", message.split()[0])
        self.assertTrue(message.rstrip().endswith((".", "!", "?")))


class ApprovedRootsTests(unittest.TestCase):
    def test_returns_absolute_paths(self):
        roots = cp.approved_roots()
        self.assertIsInstance(roots, list)
        for root in roots:
            self.assertIsInstance(root, Path)
            self.assertTrue(root.is_absolute(), root)

    def test_never_raises_and_deduplicates(self):
        roots = cp.approved_roots()
        self.assertEqual(len(roots), len(set(roots)))


if __name__ == "__main__":
    unittest.main()
