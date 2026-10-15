import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.gemini_keys import KeyPool, KeysCooling, parse_keys, retry_delay, quota_failure


class KeyTests(unittest.TestCase):
    def test_local_file_edits_are_loaded_by_existing_pool_without_printing_keys(self):
        from memory import config_manager as cfg
        from core.gemini_keys import configured_keys
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api_keys.json'
            with patch.object(cfg, 'CONFIG_FILE', path):
                path.write_text(json.dumps({'gemini_api_key': 'first,second'}))
                pool = KeyPool(configured_keys)
                self.assertEqual(pool.select(), 'first')
                pool.limited('first', '429 retry in 60s')
                self.assertEqual(pool.select(), 'second')
                pool.limited('second', '429 retry in 60s')
                path.write_text(json.dumps({'gemini_api_key': 'first,second,third,fourth'}))
                self.assertEqual(pool.select(), 'third')

    def test_comma_keys_are_trimmed_deduplicated_and_saved_without_losing_settings(self):
        from memory import config_manager as cfg
        self.assertEqual(parse_keys(' alpha, beta,, alpha,\n gamma '), ['alpha', 'beta', 'gamma'])
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'keys.json'
            path.write_text('{"voice_name":"Nika","auto_execute_owner":true}')
            with patch.object(cfg, 'CONFIG_FILE', path), patch.object(cfg, 'CONFIG_DIR', Path(folder)):
                cfg.save_api_keys('alpha, beta,alpha')
                data = cfg.load_api_keys()
                self.assertEqual(data['gemini_api_key'], 'alpha')
                self.assertEqual(data['gemini_api_keys'], ['alpha', 'beta'])
                self.assertEqual(data['voice_name'], 'Nika')
                self.assertTrue(data['auto_execute_owner'])

    def test_limited_keys_wait_and_become_available_after_provider_delay(self):
        now = [100.0]
        pool = KeyPool(lambda: ['a', 'b'], lambda: now[0])
        self.assertEqual(pool.select(), 'a')
        pool.limited('a', '429 retry in 12.5s')
        self.assertEqual(pool.select(), 'b')
        pool.limited('b', '429 retry in 20s')
        with self.assertRaises(KeysCooling) as caught:
            pool.select()
        self.assertEqual(caught.exception.retry_after, 12.5)
        self.assertEqual(pool.select('helper:other-model'), 'a')
        now[0] += 13
        self.assertEqual(pool.select(), 'a')

    def test_headers_and_nested_quota_errors_are_recognized(self):
        error = RuntimeError('429 RESOURCE_EXHAUSTED')
        error.response = Mock(headers={'Retry-After': '35'})
        nested = ExceptionGroup('background tasks', [ExceptionGroup('receive', [error])])
        self.assertIs(quota_failure(nested), error)
        self.assertEqual(retry_delay(error), 35)
        self.assertEqual(retry_delay("{'retryDelay': '8.5s'}"), 8.5)

    def test_text_generation_uses_next_key_on_429_and_stops_when_all_are_cooling(self):
        from core import gemini
        pool = KeyPool(lambda: ['a', 'b'])
        clients = []

        def client(**kwargs):
            cl = Mock()
            if kwargs['key'] == 'a':
                cl.models.generate_content.side_effect = RuntimeError('429 retry in 60s')
            else:
                cl.models.generate_content.return_value = Mock(text='answer')
            clients.append(cl)
            return cl

        with patch('core.gemini_keys.pool', pool), patch.object(gemini, 'client', side_effect=client), \
                patch.object(gemini, '_LADDERS', {gemini.FAST: ('fixture-model',)}), patch.object(gemini, '_cooldown', {}):
            self.assertEqual(gemini.call('test').text, 'answer')
            self.assertEqual(len(clients), 2)
            pool.limited('b', '429 retry in 60s', 'helper:fixture-model')
            self.assertIsNone(gemini.call('test'))
            self.assertEqual(len(clients), 2)
        for cl in clients:
            cl.close.assert_called_once()


class LiveKeyTests(unittest.IsolatedAsyncioTestCase):
    async def test_notification_voice_rotates_keys_and_respects_exhausted_pool(self):
        from core import notification_voice
        pool = KeyPool(lambda: ['a', 'b'])
        synth = AsyncMock(side_effect=[RuntimeError('429 retry in 60s'), (b'audio', 'notice')])
        with patch.object(notification_voice, 'pool', pool), patch.object(notification_voice, '_synthesize_once', synth):
            self.assertEqual(await notification_voice.synthesize_notice('fixture notice'), (b'audio', 'notice'))
            self.assertEqual([call.kwargs['key'] for call in synth.call_args_list], ['a', 'b'])
            pool.limited('b', '429 retry in 60s', 'notification')
            with self.assertRaises(KeysCooling):
                await notification_voice.synthesize_notice('fixture notice')
            self.assertEqual(synth.call_count, 2)

    async def test_live_rate_limit_rotates_key_and_all_limited_waits(self):
        from main import JarvisLive
        from google.genai import types
        from tests.test_live_listening import agent
        for keys in (['a', 'b'], ['a']):
            live = agent()
            live._conversation = None
            live._resume_handle = None
            live._enhanced_live = True
            live._session_log = []
            live._operator_notifications = AsyncMock()
            live._build_config = Mock(return_value=types.LiveConnectConfig())
            pool = KeyPool(lambda: keys)
            entered = asyncio.Event()
            client = Mock()
            attempts = []

            def connect(**_kwargs):
                attempts.append(True)
                number = len(attempts)

                class Connection:
                    async def __aenter__(self):
                        if number == 1:
                            raise ExceptionGroup('receive', [RuntimeError('429 retry in 60s')])
                        entered.set()
                        await asyncio.Event().wait()

                    async def __aexit__(self, *_):
                        pass
                return Connection()

            client.aio.live.connect.side_effect = connect
            with patch('main.gemini_keys', pool), patch('main.confirm_gate.bind'), patch('main.set_trim_notifier'), \
                    patch('main.audio_devices.configure'), patch('main.audio_devices.prefetch'), \
                    patch('dashboard.server.DashboardServer', side_effect=RuntimeError('offline fixture')), \
                    patch('main._gemini.live_model', return_value='offline-model'), \
                    patch('main.genai.Client', return_value=client), patch('main.traceback.print_exc'):
                task = asyncio.create_task(JarvisLive.run(live))
                try:
                    if len(keys) == 2:
                        await asyncio.wait_for(entered.wait(), 2)
                        self.assertEqual(pool.select(), 'b')
                        self.assertEqual(len(attempts), 2)
                    else:
                        await asyncio.sleep(.1)
                        self.assertEqual(len(attempts), 1)
                finally:
                    live.shutdown()
                    with suppress(asyncio.CancelledError):
                        await task


class KeyUIIntegrationTests(unittest.TestCase):
    def test_key_editor_saves_comma_keys_and_preserves_existing_preferences(self):
        script = '''
import json,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
from PyQt6.QtWidgets import QApplication
from ui import MainWindow
app=QApplication([])
with tempfile.TemporaryDirectory() as folder:
    path=Path(folder)/'api_keys.json'
    path.write_text(json.dumps({'gemini_api_key':'old','os_system':'windows','voice_name':'Nika','auto_execute_owner':True}))
    with patch('ui.API_FILE',path):
        w=MainWindow('face.png');w.on_credentials_change=Mock()
        w._show_setup();assert w._overlay._key_input.text()=='old'
        w._on_setup_done('alpha, beta, alpha','windows')
        data=json.loads(path.read_text())
        assert data['gemini_api_keys']==['alpha','beta'] and data['gemini_api_key']=='alpha'
        assert data['voice_name']=='Nika' and data['auto_execute_owner']
        w.on_credentials_change.assert_called_once()
        w._unsubscribe_runtime();w.close()
print('Key editor OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
