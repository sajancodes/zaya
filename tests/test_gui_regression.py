"""Regression test suite replaying observed failure scenarios.
Verifies that the agent never types into the wrong window, never performs
unverified destructive actions, and accurately reports failures instead of pretending to succeed.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

import actions.computer_control as cc
from core import gui_verifier
from core.action_loader import _call_handler
from core.tool_result import ToolResult


class TestGuiRegressionFailureReplay(unittest.TestCase):
    """Replays the failure scenario from the user log:
    User request: "Go to Facebook on Brave and add a random quote as a post."
    Failures observed:
      1. Text typed into wrong app (Antigravity IDE) because focus was unverified.
      2. Clear-first erased content in the wrong window.
      3. Partial / unverified outcomes claimed as success.
      4. Blindly clicked without post-condition verification.
      5. Parameter unpacking error in action loader passing dict as single arg.
    """

    def setUp(self):
        gui_verifier.clear_target_window()

    def tearDown(self):
        gui_verifier.clear_target_window()

    def test_window_focus_must_not_claim_success_when_window_missing(self):
        """Focusing a missing window must return an error and not claim 'Focused window'."""
        with patch("core.gui_verifier.list_visible_windows", return_value=[]):
            res = cc.computer_control({"action": "focus_window", "title": "NonExistentWindow_9999"})
            self.assertIn("focus_window failed", res)
            self.assertNotIn("Focused window: NonExistentWindow_9999", res)

    def test_smart_type_must_verify_window_before_destructive_clear(self):
        """Smart-type with target window must not clear or type if active window is wrong."""
        mock_active = {"hwnd": 100, "title": "Antigravity - Editor", "pid": 1234, "os": "windows"}
        with patch("core.gui_verifier.get_active_window_info", return_value=mock_active), \
             patch("core.gui_verifier.focus_window", return_value={"success": False, "error": "Not found"}), \
             patch("actions.computer_control.pyautogui.typewrite") as mock_type, \
             patch("actions.computer_control.pyautogui.hotkey") as mock_hotkey:

            res = cc.computer_control({
                "action": "smart_type",
                "text": "My quote text",
                "window": "Brave",
                "clear_first": True,
            })

            # Must abort and state window mismatch
            self.assertIn("ABORTED 'smart_type'", res)
            self.assertIn("Antigravity - Editor", res)
            self.assertIn("Brave", res)

            # PyAutoGUI typing and hotkey must NOT have been called
            mock_type.assert_not_called()
            mock_hotkey.assert_not_called()

    def test_clear_field_aborts_when_target_window_mismatch(self):
        """Clear-field must refuse to execute if active window is not the target."""
        mock_active = {"hwnd": 200, "title": "Visual Studio Code", "pid": 5678, "os": "windows"}
        with patch("core.gui_verifier.get_active_window_info", return_value=mock_active), \
             patch("core.gui_verifier.focus_window", return_value={"success": False, "error": "Not found"}), \
             patch("actions.computer_control.pyautogui.hotkey") as mock_hotkey, \
             patch("actions.computer_control.pyautogui.press") as mock_press:

            res = cc.computer_control({
                "action": "clear_field",
                "window": "Facebook",
            })

            self.assertIn("ABORTED 'clear_field'", res)
            mock_hotkey.assert_not_called()
            mock_press.assert_not_called()

    def test_act_and_verify_fails_loudly_when_expected_state_missing(self):
        """When an action succeeds in clicking but expected post-condition does not appear,
        it must return a failed verification status instead of claiming completed success.
        """
        with patch("actions.computer_control._click", return_value="Clicked (100, 100)"), \
             patch("actions.computer_control.pyautogui.screenshot") as mock_ss, \
             patch("actions.computer_control._find_via_ocr", return_value=None), \
             patch("actions.computer_control._find_via_uia", return_value=None), \
             patch("time.sleep"):

            mock_ss.return_value.size = (1920, 1080)
            res = cc.computer_control({
                "action": "click",
                "x": 100,
                "y": 100,
                "expect": "What's on your mind?",
                "timeout": 0.1,
            })

            self.assertIn("was NOT observed within", res)

    def test_act_and_verify_succeeds_when_expected_state_appears(self):
        """When the expected post-condition appears on screen, verification succeeds."""
        with patch("actions.computer_control._click", return_value="Clicked (100, 100)"), \
             patch("actions.computer_control.pyautogui.screenshot") as mock_ss, \
             patch("actions.computer_control._find_via_ocr", return_value=(450, 250)), \
             patch("time.sleep"):

            mock_ss.return_value.size = (1920, 1080)
            res = cc.computer_control({
                "action": "click",
                "x": 100,
                "y": 100,
                "expect": "What's on your mind?",
                "timeout": 1.0,
            })

            self.assertIn("verified post-condition", res)
            self.assertIn("What's on your mind?", res)

    def test_element_not_found_reports_truthful_failure(self):
        """When an element like 'Post' is not on screen, computer_control must return not-found."""
        with patch("actions.computer_control._screen_find", return_value=None):
            res = cc.computer_control({"action": "click", "description": "Post"})
            self.assertIn("Element not found on screen", res)

    def test_structured_tool_result_format(self):
        """Verify ToolResult contract allows honest reporting without ambiguous partial states."""
        res_fail = ToolResult(
            status="failed",
            summary="Target window 'Brave' not active (active: 'Antigravity'). Aborted typing.",
            data={"active_window": "Antigravity", "expected_window": "Brave"},
        )
        self.assertEqual(res_fail.status, "failed")
        self.assertEqual(res_fail.semantic, "FAILED")
        self.assertFalse(res_fail.data.get("verified", False))

        res_unverified = ToolResult(
            status="unverified",
            summary="Browser opened URL; page content not yet visually verified.",
            data={"url": "https://facebook.com"},
        )
        self.assertEqual(res_unverified.status, "unverified")
        self.assertEqual(res_unverified.semantic, "UNVERIFIED")

    def test_action_loader_dispatch_unpacks_explicit_kwargs(self):
        """Ensure action_loader unpacks parameters dict into declared keyword arguments."""
        def sample_action(action="status", task="", interval_sec=3.0):
            return f"Action: {action}, Task: {task}, Interval: {interval_sec}"

        params = {"task": "Monitor Facebook post creation", "action": "start", "interval_sec": 5.0}
        res = _call_handler(sample_action, params)
        self.assertEqual(res, "Action: start, Task: Monitor Facebook post creation, Interval: 5.0")

    def test_safe_clipboard_paste_preserves_user_clipboard(self):
        """safe_clipboard_paste should save prior clipboard and restore it after typing."""
        clipboard_history = []

        def mock_copy(val):
            clipboard_history.append(("copy", val))

        def mock_paste():
            return "original user text"

        with patch("pyperclip.copy", side_effect=mock_copy), \
             patch("pyperclip.paste", side_effect=mock_paste), \
             patch("pyautogui.hotkey") as mock_hotkey, \
             patch("time.sleep"):

            res = gui_verifier.safe_clipboard_paste("quote to paste")
            self.assertTrue(res["success"])
            mock_hotkey.assert_called_with("ctrl", "v")
            # First copy should be the payload, second should be the restored original
            self.assertEqual(clipboard_history[0], ("copy", "quote to paste"))
            self.assertEqual(clipboard_history[1], ("copy", "original user text"))

    def test_to_logical_coords_clamping_and_scaling(self):
        """Normalized [0..1000] coordinates must scale to screen size and clamp away from (0,0)."""
        with patch("core.gui_verifier.get_screen_metrics", return_value={
            "primary_w": 1920, "primary_h": 1080, "logical_w": 1920, "logical_h": 1080, "scale_x": 1.0, "scale_y": 1.0
        }):
            # (0, 0) normalized must be clamped to (2, 2) to prevent pyautogui failsafe
            cx, cy = gui_verifier.to_logical_coords(0, 0, 1000, 1000)
            self.assertEqual((cx, cy), (2, 2))

            # (500, 500) normalized on 1920x1080
            cx, cy = gui_verifier.to_logical_coords(500, 500, 1000, 1000)
            self.assertEqual((cx, cy), (960, 540))

            # (1000, 1000) normalized clamped to (1918, 1078)
            cx, cy = gui_verifier.to_logical_coords(1000, 1000, 1000, 1000)
            self.assertEqual((cx, cy), (1918, 1078))

    def test_browser_control_action_open_alias(self):
        """Action 'open' must be aliased to 'go_to' and not return unknown action."""
        from actions.browser_control import browser_control
        with patch("core.execution_policy.require_owner"), \
             patch("actions.browser_control._open_native", return_value="Opened in brave: https://instagram.com"):
            res = browser_control({"action": "open", "browser": "brave", "url": "https://instagram.com"})
            self.assertNotEqual(res, "Unknown action.")
            self.assertNotIn("Unknown browser action: 'open'", str(res))

    def test_browser_control_never_creates_sandboxed_zaya_profiles(self):
        """_real_profile_dir must return None if real profile is missing and never create .zaya_profiles."""
        from pathlib import Path
        from actions.browser_control import _real_profile_dir

        with patch("pathlib.Path.exists", return_value=False):
            prof = _real_profile_dir("brave")
            self.assertIsNone(prof)
            self.assertFalse(Path(Path.home() / ".zaya_profiles").exists())


if __name__ == "__main__":
    unittest.main()
