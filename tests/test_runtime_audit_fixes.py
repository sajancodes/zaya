"""Regression proof for failed vision, summary retention, and desktop UI output."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from google.genai import types

from core.gemini_keys import KeysCooling
from main import _keys_cooling_of
from memory.config_manager import _update_config
from tests.test_live_listening import agent


class RuntimeAuditTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_phone_video_recovers_without_stopping_audio_session(self):
        import queue
        live = agent()
        frames = queue.Queue()
        frames.put({'call_id': 'call', 'device_id': 'phone', 'data': b'jpeg'})
        available = SimpleNamespace(video_frames=frames)
        live._dashboard = SimpleNamespace(mobile=Mock(side_effect=[
            AttributeError('not ready'), SimpleNamespace(), available]))
        live._calls = SimpleNamespace(active=lambda: SimpleNamespace(
            state='answered', video_enabled=True, call_id='call', device_id='phone'))
        sent = asyncio.Event()

        async def send(**kwargs):
            sent.set()

        live.session = SimpleNamespace(send_realtime_input=send)
        with patch('builtins.print') as output:
            task = asyncio.create_task(live._relay_phone_video())
            try:
                await asyncio.wait_for(sent.wait(), 2)
                self.assertFalse(task.done())
                output.assert_called_once()
            finally:
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

    async def test_failed_capture_releases_vision_for_next_request(self):
        live = agent()
        live._vision_busy = False
        live._vision_last_time = 0
        live.speak_error = Mock()
        live._action_registry = Mock()
        live._action_registry.scheduling.return_value = None
        live._plugin_registry = Mock()
        live._plugin_registry.scheduling.return_value = None
        with patch('main._capture_screen', side_effect=OSError('capture failed')):
            result = await live._execute_tool_impl(types.FunctionCall(
                id='vision', name='screen_process', args={'angle': 'screen'}))
        self.assertFalse(live._vision_busy)
        self.assertIsNone(live._pending_vision)
        self.assertEqual(result.response['result']['status'], 'failed')

    async def test_failed_vision_delivery_releases_camera(self):
        live = agent()
        live._pending_vision = (b'frame', 'image/jpeg', 'Look', 'camera')
        live._vision_busy = live._vision_cam_active = True
        live.session = SimpleNamespace(send_client_content=AsyncMock(side_effect=OSError('closed')))
        with self.assertRaises(OSError):
            await live._flush_pending_vision()
        self.assertFalse(live._vision_busy)
        live.ui.stop_camera_stream.assert_called_once()

    async def test_failed_summary_retains_bounded_snapshot_and_new_turns(self):
        live = agent()
        live._session_log = [f'User: {i}' for i in range(100)]

        async def failed_summary(*args):
            live._session_log.append('User: new')
            raise OSError('offline')

        with patch('main.load_memory', return_value={}), patch('main.asyncio.to_thread', failed_summary):
            await live._save_session_summary()
        self.assertEqual(len(live._session_log), 80)
        self.assertEqual(live._session_log[-1], 'User: new')

    async def test_cancelled_summary_retains_snapshot(self):
        live = agent()
        live._session_log = ['User: one', 'Zaya: two', 'User: three']
        with patch('main.load_memory', return_value={}), patch(
                'main.asyncio.to_thread', AsyncMock(side_effect=asyncio.CancelledError)):
            with self.assertRaises(asyncio.CancelledError):
                await live._save_session_summary()
        self.assertEqual(len(live._session_log), 3)

    def test_nested_cooldown_uses_longest_provider_delay(self):
        error = ExceptionGroup('tasks', [KeysCooling(3), ExceptionGroup('inner', [KeysCooling(12)])])
        self.assertEqual(_keys_cooling_of(error).retry_after, 12)
        self.assertIsNone(_keys_cooling_of(ValueError('unrelated')))

    def test_explicit_config_path_preserves_unrelated_fields_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'settings.json'
            path.write_text(json.dumps({'voice_name': 'Nika', 'private': 'retained'}))
            _update_config(lambda data: data.update(user_name='Sajan'), path=path)
            self.assertEqual(json.loads(path.read_text())['private'], 'retained')
            path.write_text('{broken')
            with self.assertRaises(ValueError):
                _update_config(lambda data: data.clear(), path=path)
            self.assertEqual(path.read_text(), '{broken')

    def test_ui_camera_encode_failure_releases_device_and_long_log_drains(self):
        script = '''
import sys, threading
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication
from ui import MainWindow, LogWidget
app = QApplication([])
stop = Mock()
stop.wait.side_effect = [False, True]
cap = Mock()
cap.isOpened.return_value = True
cap.read.return_value = (True, object())
cv = Mock()
cv.VideoCapture.return_value = cap
cv.imencode.return_value = (False, None)
window = NS(_cam_stop=stop, _cam_stream_sig=Mock(), _cam_frame_sig=Mock())
with patch.dict(sys.modules, cv2=cv):
    MainWindow._cam_loop(window)
cap.release.assert_called_once()
window._cam_frame_sig.emit.assert_not_called()
log = LogWidget()
log.append_log('Zaya: ' + 'x' * 10000)
log.append_log('ERR: urgent')
for _ in range(400):
    log._step()
    app.processEvents()
assert 'ERR: urgent' in log.toPlainText()
print('UI audit regression checks passed')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, encoding='utf-8', timeout=30,
                                env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
