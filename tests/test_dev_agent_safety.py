"""Dev Agent safety regressions: model-written files stay inside the project.

The planner returns JSON naming the files to write, so both write sinks are
model-controlled. Traversal, absolute and UNC paths must be rejected before
anything touches disk outside the project folder.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from actions import dev_agent


class _StubModel:
    """Stands in for the Gemini wrapper so no network call happens."""

    def generate_content(self, _contents):
        return type("_Response", (), {"text": "print('ok')\n"})()


def _stub_model(_name=None):
    return _StubModel()


class ProjectContainmentTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.project = self.root / "demo"
        self.project.mkdir()
        stub = patch.object(dev_agent, "_get_model", _stub_model)
        stub.start()
        self.addCleanup(stub.stop)

    def _write(self, rel_path):
        return dev_agent._write_file(
            file_info={"path": rel_path},
            project_description="containment regression",
            all_files=[{"path": rel_path}],
            language="python",
            project_dir=self.project,
            already_written={},
        )

    def test_relative_path_writes_inside_the_project(self):
        self._write("utils/helpers.py")
        self.assertTrue((self.project / "utils" / "helpers.py").is_file())

    def test_parent_traversal_is_rejected(self):
        for rel in ("../escape.py", "sub/../../escape.py", "./a/../../../escape.py"):
            with self.subTest(rel=rel):
                with self.assertRaises(ValueError):
                    self._write(rel)
        self.assertFalse((self.root / "escape.py").exists())

    def test_windows_backslash_traversal_is_rejected(self):
        if sys.platform != "win32":
            self.skipTest("backslash separators only exist on Windows")
        with self.assertRaises(ValueError):
            self._write("..\\..\\escape.py")

    def test_absolute_path_is_rejected(self):
        target = Path.home() / "zaya_devagent_escape_check.py"
        with self.assertRaises(ValueError):
            self._write(str(target))
        self.assertFalse(target.exists())

    def test_unc_path_is_rejected(self):
        if sys.platform != "win32":
            self.skipTest("UNC paths only exist on Windows")
        with self.assertRaises(ValueError):
            self._write("\\\\server\\share\\escape.py")

    def test_empty_and_non_string_paths_are_rejected(self):
        for bad in ("", "   ", None, 7):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    self._write(bad)

    def test_fix_loop_cannot_write_outside_the_project(self):
        evil = "../fixed_escape.py"
        with patch.object(dev_agent, "_parse_traceback", return_value=(evil, 3)):
            updated = dev_agent._fix_files(
                error_output="Traceback (most recent call last):\nNameError: name 'x' is not defined",
                project_description="containment regression",
                all_files=[{"path": evil}],
                file_codes={evil: "print('broken')\n"},
                language="python",
                project_dir=self.project,
                entry_point="main.py",
            )
        self.assertEqual(updated, {})
        self.assertFalse((self.root / "fixed_escape.py").exists())


if __name__ == "__main__":
    unittest.main()
