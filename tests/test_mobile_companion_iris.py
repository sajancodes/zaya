import unittest
from core.mobile_protocol import to_wire_events, envelope
from actions.mobile_telekinesis import (
    control_incoming_call,
    manage_notification_listener,
    control_device_hardware,
    open_deep_link,
    capture_screen,
    understand_screen
)

class TestMobileCompanionIris(unittest.TestCase):
    def test_incoming_call_wire_event(self):
        events = to_wire_events('call.incoming', {
            'caller_name': 'Rahul Sharma',
            'caller_number': '+1234567890',
            'call_id': 'call_1'
        })
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'call.incoming')
        self.assertEqual(events[0]['payload']['caller_name'], 'Rahul Sharma')

    def test_notification_received_wire_event(self):
        events = to_wire_events('notification.received', {
            'app': 'whatsapp',
            'sender': 'Alex',
            'text': 'Meeting at 3pm'
        })
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'notification.received')
        self.assertEqual(events[0]['payload']['sender'], 'Alex')

    def test_screen_frame_wire_event(self):
        events = to_wire_events('screen.frame', {
            'width': 576,
            'height': 1280,
            'prompt': 'Summarize page',
            'jpeg': 'ZmFrZWpwZWc='
        })
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]['type'], 'screen.frame')
        self.assertEqual(events[0]['payload']['width'], 576)
        self.assertEqual(events[0]['payload']['prompt'], 'Summarize page')

    def test_hardware_control_action(self):
        res = control_device_hardware({"target": "flashlight", "action": "toggle"})
        self.assertIn("flashlight", res.lower())
        self.assertIn("success", res.lower())

    def test_incoming_call_controller_action(self):
        res = control_incoming_call({"action": "announce", "caller_name": "Mom"})
        self.assertIn("Mom", res)
        self.assertIn("announce", res.lower())

    def test_manage_notification_listener_action(self):
        res = manage_notification_listener({"action": "enable_auto_reply"})
        self.assertIn("auto_reply_enabled", res)

    def test_open_deep_link_action(self):
        res = open_deep_link({"target_app": "spotify", "query": "synthwave"})
        self.assertIn("spotify", res.lower())
        self.assertIn("synthwave", res.lower())

    def test_capture_screen_action(self):
        res = capture_screen({"action": "capture"})
        self.assertIn("MediaProjection", res)
        self.assertIn("success", res.lower())

    def test_understand_screen_action(self):
        res = understand_screen({"prompt": "What does this error message mean?"})
        self.assertIn("error message", res)
        self.assertIn("Gemini Multimodal Live", res)

if __name__ == "__main__":
    unittest.main()
