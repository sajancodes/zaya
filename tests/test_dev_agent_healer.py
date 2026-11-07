import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from actions.dev_agent import dev_agent, _heal_codebase


class TestDevAgentHealer(unittest.TestCase):
    @patch("actions.dev_agent._run_project")
    def test_heal_codebase_success_first_attempt(self, mock_run):
        mock_run.return_value = "============================= 5 passed in 0.20s ============================="
        res = _heal_codebase(
            project_path=str(Path.cwd()),
            check_command="python -m pytest",
            max_attempts=3,
        )
        self.assertIn("All checks passed cleanly", res)

    @patch("actions.dev_agent._run_project")
    @patch("actions.dev_agent._get_model")
    def test_heal_codebase_iterative_fix(self, mock_model, mock_run):
        # First attempt fails with SyntaxError, second passes
        mock_run.side_effect = [
            'Traceback (most recent call last):\n  File "sample_test.py", line 10\nSyntaxError: invalid syntax',
            "============================= 1 passed in 0.10s =============================",
        ]
        mock_gen = MagicMock()
        mock_gen.generate_content.return_value.text = "def test_ok():\n    assert True\n"
        mock_model.return_value = mock_gen

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "is_dir", return_value=True):
                with patch.object(Path, "read_text", return_value="def broken():\n"):
                    with patch.object(Path, "write_text") as mock_write:
                        res = _heal_codebase(
                            project_path="fake/project",
                            check_command="pytest",
                            max_attempts=3,
                        )
                        self.assertIn("All checks passed cleanly", res)
                        mock_write.assert_called_once()

    def test_dev_agent_dispatch_action_heal(self):
        with patch("actions.dev_agent._heal_codebase") as mock_heal:
            mock_heal.return_value = "Heal complete, sir."
            res = dev_agent({"action": "heal", "project_path": "."})
            self.assertEqual(res, "Heal complete, sir.")
            mock_heal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
