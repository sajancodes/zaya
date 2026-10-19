"""Tests for WorkspaceTracker context detection and event publication."""
import unittest
from unittest.mock import MagicMock, patch

from core.workspace_context import WorkspaceTracker, clean_title, extract_project_name


class TestWorkspaceContext(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(clean_title("main.py - Zaya - Visual Studio Code"), "main.py - Zaya")
        self.assertEqual(clean_title("Google - Google Chrome"), "Google")
        self.assertEqual(clean_title("Terminal"), "Terminal")
        self.assertEqual(clean_title(""), "")

    def test_extract_project_name(self):
        proj = extract_project_name("workspace_context.py - Zaya - Visual Studio Code", "Code.exe")
        self.assertEqual(proj, "Zaya")

        proj_sublime = extract_project_name("calculator.py - MyTool - Sublime Text", "sublime_text.exe")
        self.assertEqual(proj_sublime, "MyTool")

        # Unknown or non-ide process
        self.assertEqual(extract_project_name("Inbox - Outlook", "outlook.exe"), "")

    def test_workspace_tracker_event_publishing(self):
        bus = MagicMock()
        tracker = WorkspaceTracker(clock=lambda: 100.0, bus=bus)

        # Mock foreground info
        with patch.object(tracker, "get_foreground_info") as mock_info:
            mock_info.return_value = {
                "window_title": "core/workspace_context.py - Zaya - Visual Studio Code",
                "process_name": "Code.exe",
                "pid": 1234,
                "project_name": "Zaya",
            }
            res = tracker.update()
            self.assertEqual(res["project_name"], "Zaya")
            bus.publish.assert_called_once()
            call_args = bus.publish.call_args
            self.assertEqual(call_args[0][0], "workspace.changed")
            self.assertEqual(call_args[1]["project_name"], "Zaya")

            # Second update with same context should NOT publish
            bus.reset_mock()
            tracker.update()
            bus.publish.assert_not_called()

            # Context change should publish
            mock_info.return_value = {
                "window_title": "Untitled - Notepad",
                "process_name": "notepad.exe",
                "pid": 5678,
                "project_name": "",
            }
            tracker.update()
            bus.publish.assert_called_once()
            self.assertEqual(bus.publish.call_args[1]["process_name"], "notepad.exe")

    def test_tracker_snapshot_age(self):
        cur_time = 100.0
        tracker = WorkspaceTracker(clock=lambda: cur_time, bus=MagicMock())
        with patch.object(tracker, "get_foreground_info") as mock_info:
            mock_info.return_value = {
                "window_title": "Zaya",
                "process_name": "python.exe",
                "pid": 100,
                "project_name": "Zaya",
            }
            tracker.update()
            snap = tracker.snapshot()
            self.assertEqual(snap["age_seconds"], 0)

            cur_time = 145.0
            snap2 = tracker.snapshot()
            self.assertEqual(snap2["age_seconds"], 45)


if __name__ == "__main__":
    unittest.main()
