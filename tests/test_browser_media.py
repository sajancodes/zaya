from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from actions.video_player import _browser_video_url, requested_browser, video_player
from core.tool_result import ToolResult


class BrowserMediaTests(unittest.TestCase):
    def test_explicit_owner_browser_request_overrides_display_default(self):
        self.assertEqual(requested_browser('Play Ek Ladki Ko Dekha Toh by Darshan Raval on my Brave browser.'), 'brave')
        self.assertIsNone(requested_browser('Do not play on my Brave browser; use the display.'))
        self.assertIsNone(requested_browser('Play on Brave, actually play on the display.'))

    def test_exact_requested_song_opens_in_native_brave_and_closes_display(self):
        player = Mock()
        source = 'Ek Ladki Ko Dekha Toh by Darshan Raval'
        with patch('actions.video_player._browser_video_url', return_value='https://www.youtube.com/watch?v=abcdefghijk&autoplay=1') as resolve, \
                patch('actions.browser_control.browser_control', return_value=ToolResult('partial', 'launch requested')) as browser:
            result = video_player({'action': 'play', 'source': source, 'target': 'browser', 'browser': 'brave'}, player=player)
        resolve.assert_called_once_with(source)
        player.stop_video.assert_called_once()
        player.show_video.assert_not_called()
        args = browser.call_args.args[0]
        self.assertEqual(args['browser'], 'brave')
        self.assertEqual(args['mode'], 'native')
        self.assertIn('youtube.com/watch', args['url'])
        self.assertFalse(result.data['playback_verified'])

    def test_move_to_browser_reuses_current_song_instead_of_an_older_query(self):
        with patch('actions.video_player._last_source', 'The current Sanam song'), \
                patch('actions.video_player._browser_video_url', return_value='https://www.youtube.com/watch?v=abcdefghijk') as resolve, \
                patch('actions.browser_control.browser_control', return_value=ToolResult('partial', 'launch requested')):
            video_player({'action': 'move_to_browser', 'browser': 'brave'}, player=Mock())
        resolve.assert_called_once_with('The current Sanam song')

    def test_browser_lookup_uses_first_youtube_watch_result_without_media_download(self):
        search = Mock()
        search.__enter__ = Mock(return_value=search)
        search.__exit__ = Mock(return_value=False)
        search.extract_info.return_value = {'entries': [{'id': 'abcdefghijk'}]}
        with patch('yt_dlp.YoutubeDL', return_value=search):
            url = _browser_video_url('Exact song and artist')
        self.assertEqual(url, 'https://www.youtube.com/watch?v=abcdefghijk&autoplay=1')
        search.extract_info.assert_called_once_with('ytsearch1:Exact song and artist', download=False)

    def test_superseded_resolution_does_not_open_an_old_browser_request(self):
        with patch('actions.video_player._browser_video_url', return_value='https://www.youtube.com/watch?v=abcdefghijk'), \
                patch('actions.video_player._still_wanted', return_value=False), \
                patch('actions.browser_control.browser_control') as browser:
            result = video_player({'action': 'play', 'source': 'Old song', 'target': 'browser'}, player=Mock())
        browser.assert_not_called()
        self.assertEqual(result.status, 'partial')


class BrowserDestinationGuardTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_dispatch_enforces_brave_even_if_model_omits_target(self):
        from tests.test_live_listening import agent
        live = agent()
        live._operator_goal = 'Play this requested song on my Brave browser.'
        live._action_registry = Mock()
        live._action_registry.run.return_value = ToolResult('partial', 'native launch')
        live._action_registry.scheduling.return_value = None
        live._plugin_registry = Mock()
        live._plugin_registry.scheduling.return_value = None
        await live._execute_tool_impl(SimpleNamespace(name='video_player', id='fixture', args={'action': 'play', 'source': 'Exact song'}))
        sent = live._action_registry.run.call_args.args[1]
        self.assertEqual(sent['target'], 'browser')
        self.assertEqual(sent['browser'], 'brave')
        self.assertEqual(sent['source'], 'Exact song')
