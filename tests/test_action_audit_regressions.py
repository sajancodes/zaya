import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from actions import file_processor, conversation_history, desktop, code_helper, flight_finder, web_search, youtube_video
from actions import computer_settings, screen_processor, game_updater


class FileActionRegressionTests(unittest.TestCase):
    def test_shared_key_helpers_support_plural_configuration_path(self):
        modules = (file_processor, desktop, code_helper, flight_finder, web_search,
                   youtube_video, computer_settings)
        with patch('core.gemini.api_key', return_value='shared-pool-key'):
            for module in modules:
                with self.subTest(module=module.__name__):
                    self.assertEqual(module._get_api_key(), 'shared-pool-key')

    def test_camera_jpeg_failure_reports_capture_error_and_releases_camera(self):
        capture = Mock()
        capture.isOpened.return_value = True
        capture.read.return_value = (True, object())
        with patch.object(screen_processor, '_PIL', False), \
                patch.object(screen_processor, '_CV2', True), \
                patch.object(screen_processor, '_get_camera_index', return_value=0), \
                patch.object(screen_processor, '_cv2_backend', return_value=0), \
                patch.object(screen_processor.cv2, 'VideoCapture', return_value=capture), \
                patch.object(screen_processor.cv2, 'imencode', return_value=(False, None)):
            with self.assertRaisesRegex(RuntimeError, 'encoded as JPEG'):
                screen_processor._capture_camera()
        capture.release.assert_called_once()

    def test_external_messages_cannot_approve_generated_desktop_code(self):
        from core.execution_policy import with_trust, TRUST_EXTERNAL_MESSAGE
        with with_trust(TRUST_EXTERNAL_MESSAGE), patch('core.confirm.request') as gate:
            with self.assertRaises(PermissionError):
                desktop._execute_generated_code('print("no")')
        gate.assert_not_called()

    def test_brightness_uses_display_name_as_data_and_clamps_value(self):
        report = 'HDMI-0 connected primary\n    Brightness: 0.95\n'
        with patch.object(computer_settings.subprocess, 'run',
                          return_value=SimpleNamespace(stdout=report)) as run:
            computer_settings._adjust_xrandr_brightness(0.1)
        self.assertEqual(run.call_args.args[0],
                         ['xrandr', '--output', 'HDMI-0', '--brightness', '1.0'])
        self.assertNotIn('shell', run.call_args.kwargs)

    def test_screen_settings_use_atomic_shared_writer(self):
        with patch('memory.config_manager._patch_config') as save:
            screen_processor._save_config_key('camera_index', 2)
        save.assert_called_once_with(camera_index=2)

    def test_epic_update_all_does_not_launch_games(self):
        games = [{'id': str(i), 'name': f'game {i}'} for i in range(12)]
        with patch.object(game_updater, '_get_epic_games', return_value=games), \
                patch.object(game_updater, '_is_epic_running', return_value=True), \
                patch.object(game_updater, 'is_mac', return_value=False), \
                patch.object(game_updater, 'is_linux', return_value=False), \
                patch.object(game_updater.subprocess, 'Popen') as launch:
            result = game_updater._update_epic_games(Path('Epic.exe'))
        launch.assert_called_once_with(['Epic.exe'])
        self.assertIn('no games were launched', result)

    def test_flight_query_has_requested_date_and_no_old_encoded_itinerary(self):
        url = flight_finder._build_google_flights_url('KTM & DEL', 'LHR', '2026-12-01')
        query = parse_qs(urlsplit(url).query)
        self.assertNotIn('tfs', query)
        self.assertIn('KTM & DEL', query['q'][0])
        self.assertIn('2026-12-01', query['q'][0])

    def test_empty_search_candidates_are_empty_text(self):
        self.assertEqual(web_search._response_text(SimpleNamespace(candidates=[])), '')
        self.assertEqual(web_search._response_text(SimpleNamespace(candidates=[SimpleNamespace(content=None)])), '')

    def test_transcript_supports_current_library_and_snippet_objects(self):
        class Transcript:
            def fetch(self):
                return [SimpleNamespace(text='hello'), SimpleNamespace(text='world')]
        listing = SimpleNamespace(find_manually_created_transcript=lambda languages: Transcript())
        class Api:
            def list(self, video_id):
                return listing
        with patch.object(youtube_video, 'YouTubeTranscriptApi', Api), \
                patch.object(youtube_video, '_TRANSCRIPT_OK', True):
            self.assertEqual(youtube_video._get_transcript('example'), 'hello world')

    def test_generated_desktop_code_waits_for_interface_gate(self):
        with patch('core.confirm.request', return_value='pending') as gate, \
                patch.object(desktop, '_run_generated_code') as run:
            self.assertEqual(desktop._execute_generated_code('print("safe")'), 'pending')
            run.assert_not_called()
            gate.call_args.args[3]()
            run.assert_called_once_with('print("safe")')

    def test_organization_can_be_undone_without_overwriting_new_files(self):
        from core import undo
        undo.clear()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'notes.txt').write_text('original', encoding='utf-8')
            with patch.object(desktop, '_get_desktop', return_value=root):
                desktop.organize_desktop()
            self.assertFalse((root / 'notes.txt').exists())
            undo.undo_last()
            self.assertEqual((root / 'notes.txt').read_text(encoding='utf-8'), 'original')

    def test_successful_stderr_does_not_trigger_code_repair(self):
        output = code_helper._ExecutionOutput('Stderr:\nwarning: fallback used', 0)
        self.assertFalse(code_helper._has_error(output))
        self.assertTrue(code_helper._has_error(code_helper._ExecutionOutput('', 1)))

    def test_unknown_text_action_retains_requested_instruction(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.txt'
            path.write_text('Document content', encoding='utf-8')
            model = SimpleNamespace(generate_content=lambda prompt: SimpleNamespace(text=prompt))
            with patch.object(file_processor, '_gemini_client', return_value=model):
                result = file_processor._process_text_doc(path, 'txt', 'rewrite politely', {})
        self.assertTrue(result.startswith('rewrite politely\n\nDocument content'))

    def test_python_run_uses_active_interpreter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'hello.py'
            path.write_text('print("hello")', encoding='utf-8')
            with patch.object(file_processor.subprocess, 'run', return_value=SimpleNamespace(stdout='hello', stderr='')) as run:
                file_processor._process_code(path, 'run', {})
            self.assertEqual(run.call_args.args[0][0], file_processor.sys.executable)

    def test_history_truncation_keeps_start_of_message(self):
        store = SimpleNamespace(chat_id='test', recent=lambda **kw: [{'text': 'START' + 'a' * 5000 + 'END'}])
        with patch.object(conversation_history, 'ConversationStore', return_value=store), \
                patch.object(conversation_history, 'require_owner'):
            result = conversation_history.conversation_history({})
        text = result.data['messages'][0]['text']
        self.assertTrue(text.startswith('START'))
        self.assertEqual(len(text), 4000)
