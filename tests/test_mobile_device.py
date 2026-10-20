"""Unit tests for actions/mobile_device.py, mobile bridge correlation, and real screen vision.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, patch

from actions.mobile_device import (
    capture_phone_screen,
    control_device_hardware,
    control_incoming_call,
    control_phone_media,
    get_phone_awareness_summary,
    make_phone_call,
    manage_phone_notifications,
    open_phone_app,
    search_phone_contacts,
    send_sms_message,
    understand_phone_screen,
    _on_phone_call,
    _on_phone_hardware,
    _on_phone_notification,
)
from core.llm.types import ImagePart, LLMMessage, LLMResponse
from core.tool_result import ToolResult


class TestMobileDeviceActions(unittest.TestCase):

    def setUp(self):
        # Set owner environment variable so require_owner() succeeds
        self.owner_patch = patch.dict("os.environ", {"ZAYA_OWNER_OVERRIDE": "1"})
        self.owner_patch.start()

    def tearDown(self):
        self.owner_patch.stop()

    def test_hardware_control_simulation_fallback(self):
        """When no phone is connected, hardware control provides safe simulation feedback."""
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 0
            mock_bridge.return_value = bridge_inst

            res = control_device_hardware({"target": "flashlight", "action": "on"})
            self.assertEqual(res.status, "success")
            self.assertIn("flashlight turned on", res.summary)

            res_vol = control_device_hardware({"target": "volume", "percent": 75})
            self.assertEqual(res_vol.status, "success")
            self.assertIn("75%", res_vol.summary)

    def test_hardware_control_connected(self):
        """When phone is connected, dispatches action over bridge."""
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success", "target": "flashlight", "state": True}
            mock_bridge.return_value = bridge_inst

            res = control_device_hardware({"target": "flashlight", "action": "on"})
            self.assertEqual(res.status, "success")
            bridge_inst.dispatch_phone_action.assert_called_with("set_flashlight", {"enabled": True})

    def test_open_phone_app(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success", "package": "com.google.android.youtube"}
            mock_bridge.return_value = bridge_inst

            res = open_phone_app({"target_app": "youtube", "query": "lofi beats"})
            self.assertEqual(res.status, "success")
            self.assertIn("Launched 'youtube'", res.summary)
            bridge_inst.dispatch_phone_action.assert_called_with("launch_app", {"name": "youtube", "query": "lofi beats"})

    def test_control_phone_media(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success"}
            mock_bridge.return_value = bridge_inst

            res = control_phone_media({"action": "pause"})
            self.assertEqual(res.status, "success")
            bridge_inst.dispatch_phone_action.assert_called_with("control_media", {"action": "pause"})

    def test_search_phone_contacts(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {
                "status": "success",
                "contacts": [{"name": "Sajan Rai", "number": "+1234567890"}]
            }
            mock_bridge.return_value = bridge_inst

            res = search_phone_contacts({"query": "Sajan"})
            self.assertEqual(res.status, "success")
            self.assertIn("Found 1 matching contact", res.summary)

    def test_make_phone_call(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success"}
            mock_bridge.return_value = bridge_inst

            res = make_phone_call({"contact": "Sajan Rai"})
            self.assertEqual(res.status, "success")
            self.assertIn("Placing cellular phone call", res.summary)

    def test_control_incoming_call(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success"}
            mock_bridge.return_value = bridge_inst

            res_answer = control_incoming_call({"action": "answer", "caller_name": "Mom"})
            self.assertEqual(res_answer.status, "success")
            bridge_inst.dispatch_phone_action.assert_called_with("answer_call", {})

            res_reject = control_incoming_call({"action": "reject", "caller_name": "Unknown"})
            self.assertEqual(res_reject.status, "success")
            bridge_inst.dispatch_phone_action.assert_called_with("reject_call", {})

    def test_send_sms_message(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success"}
            mock_bridge.return_value = bridge_inst

            res = send_sms_message({"contact": "+1234567890", "message": "I will be home soon."})
            self.assertEqual(res.status, "success")
            self.assertIn("SMS sent to +1234567890", res.summary)

    def test_manage_phone_notifications_reply(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_phone_action.return_value = {"status": "success"}
            mock_bridge.return_value = bridge_inst

            res = manage_phone_notifications({
                "action": "reply",
                "key": "notif_001",
                "reply_text": "Sounds good!"
            })
            self.assertEqual(res.status, "success")
            bridge_inst.dispatch_phone_action.assert_called_with("reply_notification", {"key": "notif_001", "text": "Sounds good!"})

    def test_unified_awareness_summary(self):
        # Push mock event to cache
        _on_phone_call({"type": "call.incoming", "caller_name": "Alice", "caller_number": "555-0101"})
        _on_phone_notification({"app": "whatsapp", "sender": "Bob", "text": "Let's meet tomorrow."})
        _on_phone_hardware({"battery": 92, "target": "flashlight", "state": "off"})

        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            mock_bridge.return_value = bridge_inst

            res = get_phone_awareness_summary({})
            self.assertEqual(res.status, "success")
            self.assertIn("Companion Phone Status", res.summary)
            self.assertIn("Battery: 92%", res.summary)
            self.assertIn("Alice", res.summary)
            self.assertIn("Bob", res.summary)

    def test_capture_phone_screen(self):
        with patch("actions.mobile_device.get_bridge") as mock_bridge:
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_screen_capture.return_value = {
                "status": "success",
                "width": 1080,
                "height": 2400,
                "jpeg": "fake_jpeg_base64"
            }
            mock_bridge.return_value = bridge_inst

            res = capture_phone_screen({"prompt": "Inspect active app"})
            self.assertEqual(res.status, "success")
            self.assertIn("1080x2400", res.summary)

    def test_real_multimodal_screen_understanding(self):
        """Validates that understand_phone_screen executes genuine multimodal AI vision pipeline."""
        fake_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        b64_jpeg = base64.b64encode(fake_jpeg).decode("ascii")

        with patch("actions.mobile_device.get_bridge") as mock_bridge, \
             patch("actions.mobile_device.LLMRouter") as mock_router_cls:

            # Mock bridge returning phone screen frame
            bridge_inst = MagicMock()
            bridge_inst.sink_count.return_value = 1
            bridge_inst.dispatch_screen_capture.return_value = {
                "status": "success",
                "width": 1080,
                "height": 2400,
                "jpeg": b64_jpeg
            }
            mock_bridge.return_value = bridge_inst

            # Mock LLMRouter executing multimodal vision
            router_inst = MagicMock()
            router_inst.route.return_value = LLMResponse(
                content="The phone screen is currently displaying Google Maps showing driving directions to Downtown.",
                provider="gemini",
                model="gemini-2.0-flash",
                usage={"prompt_tokens": 150, "completion_tokens": 20}
            )
            mock_router_cls.return_value = router_inst

            res = understand_phone_screen({"prompt": "What app is open?"})

            # Assert outcome
            self.assertEqual(res.status, "success")
            self.assertIn("Google Maps", res.summary)
            self.assertEqual(res.data.get("provider"), "gemini")
            self.assertEqual(res.data.get("model"), "gemini-2.0-flash")

            # Verify router was called with task="vision" and the actual ImagePart
            router_inst.route.assert_called_once()
            call_kwargs = router_inst.route.call_args[1]
            self.assertEqual(call_kwargs.get("task"), "vision")
            messages = call_kwargs.get("messages")
            self.assertEqual(len(messages), 1)
            msg_parts = messages[0].content
            self.assertEqual(msg_parts[0], "What app is open?")
            self.assertIsInstance(msg_parts[1], ImagePart)
            self.assertEqual(msg_parts[1].data, fake_jpeg)
            self.assertEqual(msg_parts[1].mime_type, "image/jpeg")


if __name__ == "__main__":
    unittest.main()
