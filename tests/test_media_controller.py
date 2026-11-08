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

    @patch("actions.media_controller.fade_volume")
    def test_control_media_playback_fade(self, mock_fade):
        mock_fade.return_value = True
        res = control_media_playback({"action": "fade_out", "target": 0, "duration": 0.5})
        self.assertIn("faded down", res.lower())
        mock_fade.assert_called_with(0, duration_seconds=0.5)

    @patch("actions.computer_settings.volume_get", return_value=80)
    @patch("actions.computer_settings.volume_set")
    def test_duck_and_unduck(self, mock_set, mock_get):
        from actions.media_controller import duck_volume, unduck_volume
        assert duck_volume(target_percent=20) is True
        assert unduck_volume() is True
        mock_set.assert_called()

class TestCalendarScheduler(unittest.TestCase):
    def test_add_and_list_event(self):
        evt = add_event(
            title="Design Review",
            hours_from_now=2.0,
            duration_minutes=45,
            add_meet=True
        )
        self.assertEqual(evt["title"], "Design Review")
        self.assertEqual(evt["sync_status"], "local_only")

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
        self.assertIn("local_only", res)

if __name__ == "__main__":
    unittest.main()
