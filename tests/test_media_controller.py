import unittest
from unittest.mock import patch, MagicMock
from actions.media_controller import control_media_playback, dispatch_media_key, VK_MEDIA
from actions.calendar_scheduler import calendar_schedule, list_events, add_event, delete_event

class TestMediaController(unittest.TestCase):
    @patch("actions.media_controller.dispatch_media_key")
    def test_control_media_playback_play_pause(self, mock_dispatch):
        mock_dispatch.return_value = True
        res = control_media_playback({"action": "toggle"})
        self.assertIn("toggle", res.lower())
        mock_dispatch.assert_called_with("toggle")

    @patch("actions.media_controller.dispatch_media_key")
    def test_control_media_playback_next(self, mock_dispatch):
        mock_dispatch.return_value = True
        res = control_media_playback({"action": "next"})
        self.assertIn("next", res.lower())
        mock_dispatch.assert_called_with("next")

    def test_vk_media_codes_defined(self):
        self.assertIn("play_pause", VK_MEDIA)
        self.assertIn("next", VK_MEDIA)
        self.assertIn("prev", VK_MEDIA)
        self.assertIn("mute", VK_MEDIA)

class TestCalendarScheduler(unittest.TestCase):
    def test_add_and_list_event(self):
        evt = add_event(
            title="Design Review",
            hours_from_now=2.0,
            duration_minutes=45,
            add_meet=True
        )
        self.assertIn("meet.google.com", evt.get("meet_link", ""))
        self.assertEqual(evt["title"], "Design Review")

        events = list_events(within_hours=48.0)
        titles = [e["title"] for e in events]
        self.assertIn("Design Review", titles)

        # Cleanup
        delete_event(evt["id"])

    def test_calendar_schedule_action(self):
        res = calendar_schedule({
            "action": "schedule",
            "title": "Sync meeting",
            "hours_from_now": 1.0,
            "duration_minutes": 30
        })
        self.assertIn("Sync meeting", res)
        self.assertIn("meet.google.com", res)

if __name__ == "__main__":
    unittest.main()
