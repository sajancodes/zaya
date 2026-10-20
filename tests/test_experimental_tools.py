"""Unit tests for Group G experimental tools: wormhole tunnel, ghost keyboard, ghost overlay, and screen peeler.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from actions.ghost_keyboard import ghost_keyboard, send_hotkey, inject_text
from actions.ghost_overlay import ghost_overlay
from actions.port_tunnel import deploy_wormhole, _active_tunnels
from actions.screen_peeler import screen_peeler
from core.tool_result import ToolResult


class TestExperimentalTools(unittest.TestCase):

    def setUp(self):
        self.owner_patch = patch.dict("os.environ", {"ZAYA_OWNER_OVERRIDE": "1"})
        self.owner_patch.start()

    def tearDown(self):
        self.owner_patch.stop()
        _active_tunnels.clear()

    # ── Port Tunnel ──────────────────────────────────────────────────────────

    @patch("actions.port_tunnel.start_tunnel_process")
    def test_deploy_wormhole_start(self, mock_start):
        mock_start.return_value = {
            "status": "success",
            "port": 3000,
            "tunnel_url": "https://zaya-wormhole-demo.trycloudflare.com",
            "provider": "cloudflared",
            "message": "Wormhole active: Localhost port 3000 exposed at https://zaya-wormhole-demo.trycloudflare.com"
        }
        res = deploy_wormhole({"action": "start", "port": 3000})
        self.assertEqual(res.status, "success")
        self.assertIn("https://zaya-wormhole-demo.trycloudflare.com", res.summary)

    @patch("actions.port_tunnel.stop_tunnel_process")
    def test_deploy_wormhole_stop(self, mock_stop):
        mock_stop.return_value = {"status": "success", "message": "Closed wormhole tunnel on port 3000."}
        res = deploy_wormhole({"action": "stop", "port": 3000})
        self.assertEqual(res.status, "success")
        self.assertIn("Closed wormhole tunnel", res.summary)

    def test_deploy_wormhole_list(self):
        res = deploy_wormhole({"action": "status"})
        self.assertEqual(res.status, "success")
        self.assertIn("No active port tunnels", res.summary)

    # ── Ghost Keyboard ───────────────────────────────────────────────────────

    @patch("actions.ghost_keyboard.send_hotkey", return_value=True)
    def test_ghost_keyboard_hotkey(self, mock_hotkey):
        res = ghost_keyboard({"hotkey": "ctrl+c"})
        self.assertEqual(res.status, "success")
        self.assertIn("Injected hotkey: ctrl+c", res.summary)
        mock_hotkey.assert_called_with("ctrl+c")

    @patch("actions.ghost_keyboard.inject_text", return_value=True)
    def test_ghost_keyboard_typing(self, mock_typing):
        res = ghost_keyboard({"text": "Hello Zaya", "delay_ms": 5})
        self.assertEqual(res.status, "success")
        self.assertIn("Typed 10 characters", res.summary)
        mock_typing.assert_called_with("Hello Zaya", delay_ms=5)

    def test_ghost_keyboard_missing_args(self):
        res = ghost_keyboard({})
        self.assertEqual(res.status, "failed")
        self.assertIn("No text or hotkey", res.summary)

    # ── Ghost Overlay ────────────────────────────────────────────────────────

    def test_ghost_overlay_toggle(self):
        res_open = ghost_overlay({"action": "open"})
        self.assertEqual(res_open.status, "success")
        self.assertTrue(res_open.data.get("visible"))

        res_close = ghost_overlay({"action": "close"})
        self.assertEqual(res_close.status, "success")
        self.assertFalse(res_close.data.get("visible"))

    # ── Screen Peeler ────────────────────────────────────────────────────────

    @patch("actions.screen_peeler.extract_text_from_region")
    @patch("pyperclip.copy")
    def test_screen_peeler_extract(self, mock_copy, mock_extract):
        mock_extract.return_value = "const server = express();"
        res = screen_peeler({"region": [100, 100, 500, 400]})
        self.assertEqual(res.status, "success")
        self.assertIn("ScreenPeeler extracted 25 characters", res.summary)
        self.assertEqual(res.data.get("extracted_text"), "const server = express();")

    @patch("actions.screen_peeler.extract_text_from_region", return_value="")
    def test_screen_peeler_empty(self, mock_extract):
        res = screen_peeler({})
        self.assertEqual(res.status, "failed")
        self.assertIn("no text could be extracted", res.summary)


if __name__ == "__main__":
    unittest.main()
