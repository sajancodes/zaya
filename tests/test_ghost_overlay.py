import unittest
from unittest.mock import patch, MagicMock
from actions.ghost_overlay import ghost_overlay
from actions.ghost_keyboard import ghost_keyboard

class TestGhostTools(unittest.TestCase):
    @patch("actions.ghost_overlay.toggle_ghost_overlay_window")
    def test_ghost_overlay_toggle(self, mock_toggle):
        mock_toggle.return_value = {"status": "success", "visible": True, "position": [500, 300]}
        res = ghost_overlay({"action": "toggle"})
        self.assertIn("Ghost Mini Overlay dock", res)

    @patch("actions.ghost_keyboard.inject_text")
    def test_ghost_keyboard_typing(self, mock_inject):
        mock_inject.return_value = True
        res = ghost_keyboard({"text": "Hello world from Ghost Typer!"})
        self.assertIn("Typed 29 characters", res)
        mock_inject.assert_called_with("Hello world from Ghost Typer!", delay_ms=10)

    @patch("actions.ghost_keyboard.send_hotkey")
    def test_ghost_keyboard_hotkey(self, mock_hotkey):
        mock_hotkey.return_value = True
        res = ghost_keyboard({"hotkey": "ctrl+alt+space"})
        self.assertIn("Injected hotkey", res)
        mock_hotkey.assert_called_with("ctrl+alt+space")

if __name__ == "__main__":
    unittest.main()
