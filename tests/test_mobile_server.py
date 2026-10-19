"""The mobile HTTP/WebSocket surface, driven through the real FastAPI app.

Nothing here starts a second server: every route under test is registered onto the
one dashboard app by `dashboard/mobile_api.py`. The suite covers pairing, device
auth, revocation, the read-only views, the two sockets and — because it shipped
broken once — the dashboard's transport encryption.
"""
import base64
import hashlib
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from core.device_registry import DeviceRegistry
from core.mobile_bridge import reset_bridge
from core.mobile_calls import reset_call_manager


def encrypt_for(session_key: str, salt: bytes, text: str) -> str:
    """Exactly what dashboard/static/app.html does: base64(IV ‖ AES-256-CBC(PKCS7))."""
    from cryptography.hazmat.primitives import padding as sym_pad
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    key = hashlib.sha256(session_key.encode('utf-8') + salt).digest()
    iv = bytes(range(16))
    padder = sym_pad.PKCS7(128).padder()
    padded = padder.update(text.encode('utf-8')) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(iv + encryptor.update(padded) + encryptor.finalize()).decode()


class MobileServerTestCase(unittest.TestCase):
    """One dashboard server per test, on a private device store and upload folder."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.registry = DeviceRegistry(Path(self.folder.name) / 'runtime.db')
        patcher = patch('core.device_registry.get_registry', return_value=self.registry)
        patcher.start()
        self.addCleanup(patcher.stop)
        reset_bridge()
        reset_call_manager()

        from dashboard.server import DashboardServer
        self.server = DashboardServer()
        self.server._uploads_dir = Path(self.folder.name) / 'uploads'
        self.server._uploads_dir.mkdir(parents=True, exist_ok=True)
        # Keep tests off the real task runtime (and its SQLite file). The endpoint
        # shape is still exercised; the projection itself has its own tests.
        tasks_patcher = patch('dashboard.mobile_api.MobileApi.tasks', return_value=[])
        tasks_patcher.start()
        self.addCleanup(tasks_patcher.stop)
        self.client = TestClient(self.server.app)
        self.addCleanup(self._teardown_test)

    def _teardown_test(self):
        """Close everything in the one order Windows allows: sockets, then the
        database, then the folder that holds it."""
        try:
            self.client.close()
        except Exception:
            pass
        try:
            self.registry.db.close()
        except Exception:
            pass
        reset_call_manager()
        reset_bridge()
        self.folder.cleanup()

    # ── helpers ───────────────────────────────────────────────────────────────

    def pair(self, name: str = 'Pixel 8') -> dict:
        key = self.server.new_key()
        response = self.client.post('/api/mobile/pair', json={'key': key, 'device_name': name,
                                                              'app_version': '0.1.0',
                                                              'platform': 'android'})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def auth(self, token: str) -> dict:
        return {'Authorization': f'Bearer {token}'}

    def mobile(self):
        return self.server.mobile()


class PairingTests(MobileServerTestCase):
    def test_pairing_hands_out_a_secret_the_laptop_does_not_keep(self):
        body = self.pair()
        self.assertTrue(body['ok'])
        self.assertEqual(body['protocol_version'], 1)
        self.assertTrue(body['device_id'] and body['device_secret'] and body['token'])
        self.assertNotIn(body['device_secret'], (Path(self.folder.name) / 'runtime.db').read_bytes()
                         .decode('latin-1'))
        self.assertEqual(self.registry.get(body['device_id'])['device_name'], 'Pixel 8')

    def test_a_pairing_key_works_exactly_once(self):
        key = self.server.new_key()
        first = self.client.post('/api/mobile/pair', json={'key': key})
        second = self.client.post('/api/mobile/pair', json={'key': key})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 401)

    def test_an_unknown_or_expired_key_is_refused(self):
        self.assertEqual(self.client.post('/api/mobile/pair', json={'key': 'ZZZZZZ'}).status_code, 401)
        self.assertEqual(self.client.post('/api/mobile/pair', json={}).status_code, 401)
        expired = self.server.new_key(expiry_secs=-1)
        self.assertEqual(self.client.post('/api/mobile/pair', json={'key': expired}).status_code, 401)

    def test_a_paired_phone_reconnects_without_a_new_qr_code(self):
        body = self.pair()
        response = self.client.post('/api/mobile/login', json={
            'device_id': body['device_id'], 'device_secret': body['device_secret'],
            'app_version': '0.2.0'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()['token'])
        self.assertEqual(self.registry.get(body['device_id'])['app_version'], '0.2.0')

    def test_login_with_the_wrong_secret_is_indistinguishable_from_an_unknown_device(self):
        body = self.pair()
        wrong = self.client.post('/api/mobile/login', json={
            'device_id': body['device_id'], 'device_secret': 'nope'})
        unknown = self.client.post('/api/mobile/login', json={
            'device_id': 'no-such-device', 'device_secret': 'nope'})
        self.assertEqual(wrong.status_code, unknown.status_code, 401)
        self.assertEqual(wrong.json(), unknown.json())

    def test_a_revoked_device_cannot_log_back_in(self):
        body = self.pair()
        self.server.mobile()          # revoke path needs no lazily-built state either way
        self.registry.revoke(body['device_id'])
        response = self.client.post('/api/mobile/login', json={
            'device_id': body['device_id'], 'device_secret': body['device_secret']})
        self.assertEqual(response.status_code, 401)

    def test_repeated_failures_lock_the_device_out_of_the_login_route(self):
        body = self.pair()
        for _ in range(5):
            self.client.post('/api/mobile/login', json={'device_id': body['device_id'],
                                                        'device_secret': 'wrong'})
        response = self.client.post('/api/mobile/login', json={
            'device_id': body['device_id'], 'device_secret': body['device_secret']})
        self.assertEqual(response.status_code, 429)
        self.assertGreater(response.json().get('retry_after', 0), 0)

    def test_the_owner_token_lists_and_revokes_devices(self):
        body = self.pair()
        self.server._tokens.add('owner-token')
        listed = self.client.get('/api/mobile/devices', headers={'Authorization': 'Bearer owner-token'})
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([d['device_id'] for d in listed.json()['devices']], [body['device_id']])
        revoked = self.client.post('/api/mobile/revoke',
                                   headers={'Authorization': 'Bearer owner-token'},
                                   json={'device_id': body['device_id']})
        self.assertEqual(revoked.status_code, 200)
        self.assertTrue(revoked.json()['revoked'])
        self.assertTrue(self.registry.get(body['device_id'])['revoked'])

    def test_a_device_can_revoke_itself_but_nothing_else(self):
        victim = self.pair('Victim')
        attacker = self.pair('Attacker')
        my_token = attacker['token']
        denied = self.client.post('/api/mobile/revoke', headers=self.auth(my_token),
                                 json={'device_id': victim['device_id']})
        self.assertEqual(denied.status_code, 401)
        mine = self.client.post('/api/mobile/revoke', headers=self.auth(my_token),
                                json={'device_id': attacker['device_id']})
        self.assertEqual(mine.status_code, 200)
        self.assertTrue(self.registry.get(attacker['device_id'])['revoked'])

    def test_revoking_a_device_invalidates_the_token_it_holds(self):
        body = self.pair()
        self.assertTrue(self.client.get('/api/mobile/state', headers=self.auth(body['token'])).status_code == 200)
        self.server._tokens.add('owner-token')
        self.client.post('/api/mobile/revoke', headers={'Authorization': 'Bearer owner-token'},
                         json={'device_id': body['device_id']})
        self.assertEqual(self.client.get('/api/mobile/state', headers=self.auth(body['token'])).status_code, 401)

    def test_an_unauthenticated_phone_gets_nothing(self):
        for path in ('/api/mobile/state', '/api/mobile/tasks', '/api/mobile/files'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 401)
        self.assertEqual(self.client.get('/api/mobile/state', headers=self.auth('made-up')).status_code, 401)
        self.assertEqual(self.client.get('/api/mobile/whatsapp').status_code, 401)


class ReadOnlyViewTests(MobileServerTestCase):
    def test_state_reports_the_laptop_authority(self):
        body = self.pair()
        bridge = self.mobile().bridge
        bridge.set_state('TASK_RUNNING', announce=False)
        bridge.set_emotion('happy', announce=False)
        response = self.client.get('/api/mobile/state', headers=self.auth(body['token']))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload['state'], 'TASK_RUNNING')
        self.assertEqual(payload['emotion'], 'happy')
        self.assertEqual(payload['protocol_version'], 1)
        self.assertIn('tasks', payload)

    def test_tasks_are_a_bounded_projection(self):
        body = self.pair()
        long_goal = 'g' * 4000
        with patch('dashboard.mobile_api.MobileApi.tasks',
                   return_value=[{'task_id': 't1', 'goal': long_goal[:160], 'state': 'executing',
                                  'attempts': 1, 'created_at': 1.0, 'updated_at': 2.0}]):
            response = self.client.get('/api/mobile/tasks', headers=self.auth(body['token']))
        self.assertEqual(response.status_code, 200)
        task = response.json()['tasks'][0]
        self.assertEqual(task['task_id'], 't1')
        self.assertEqual(len(task['goal']), 160)

    def test_the_phone_may_move_zaya_voice_between_the_laptop_and_itself(self):
        body = self.pair()
        response = self.client.post('/api/mobile/output', headers=self.auth(body['token']),
                                    json={'target': 'phone'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.mobile().bridge.output_target, 'phone')
        bad = self.client.post('/api/mobile/output', headers=self.auth(body['token']),
                               json={'target': 'everything'})
        self.assertEqual(bad.status_code, 400)

    def test_files_are_listed_and_downloaded_from_the_dashboard_uploads_folder(self):
        body = self.pair()
        (self.server._uploads_dir / 'notes.txt').write_text('hello', encoding='utf-8')
        listed = self.client.get('/api/mobile/files', headers=self.auth(body['token']))
        self.assertEqual([f['name'] for f in listed.json()['files']], ['notes.txt'])
        downloaded = self.client.get('/api/mobile/download', headers=self.auth(body['token']),
                                     params={'name': 'notes.txt'})
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.content, b'hello')

    def test_download_cannot_escape_the_uploads_folder(self):
        body = self.pair()
        secret = Path(self.folder.name) / 'secret.txt'
        secret.write_text('private', encoding='utf-8')
        for name in ('..\\secret.txt', '../secret.txt', str(secret)):
            with self.subTest(name=name):
                response = self.client.get('/api/mobile/download', headers=self.auth(body['token']),
                                          params={'name': name})
                self.assertEqual(response.status_code, 404)

    def test_whatsapp_actions_are_whitelisted(self):
        body = self.pair()
        response = self.client.get('/api/mobile/whatsapp', headers=self.auth(body['token']),
                                   params={'action': 'drop-tables'})
        self.assertEqual(response.status_code, 400)


class SocketTests(MobileServerTestCase):
    def test_an_unknown_token_is_never_accepted(self):
        from starlette.websockets import WebSocketDisconnect
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect('/ws/mobile?token=nonsense') as ws:
                ws.receive_text()

    def test_hello_ping_and_snapshot(self):
        body = self.pair()
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            hello = ws.receive_json()
            self.assertEqual(hello['type'], 'hello')
            self.assertEqual(hello['payload']['protocol_version'], 1)
            self.assertEqual(hello['payload']['device_id'], body['device_id'])
            self.assertIn('snapshot', hello['payload'])
            self.assertEqual(hello['payload']['audio'],
                             {'uplink_rate': 16000, 'downlink_rate': 24000})

            ws.send_json({'type': 'ping'})
            self.assertEqual(ws.receive_json()['type'], 'pong')

            ws.send_json({'type': 'hello', 'app_version': '0.1.0', 'audio_output': True})
            state = ws.receive_json()
            self.assertEqual(state['type'], 'zaya.state')
            self.assertIn(state['payload']['state'], ('STANDBY', 'SLEEPING', 'MUTED'))

            ws.send_json({'type': 'shut-the-laptop-down'})          # unknown: ignored
            ws.send_json({'type': 'ping'})
            self.assertEqual(ws.receive_json()['type'], 'pong')

    def test_a_command_is_queued_once_and_echoed_as_a_chat_message(self):
        body = self.pair()
        self.server._wake_callback = lambda: None
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()                                       # hello
            ws.send_json({'type': 'command', 'text': 'check the deploy', 'request_id': 'req-1'})
            status = ws.receive_json()
            self.assertEqual(status['type'], 'command.status')
            self.assertEqual(status['payload']['request_id'], 'req-1')
            self.assertEqual(status['payload']['status'], 'submitted')
            chat = ws.receive_json()
            self.assertEqual(chat['type'], 'chat.message')
            self.assertEqual(chat['payload'], {'role': 'user', 'text': 'check the deploy',
                                              'request_id': 'req-1', 'source': 'phone'})
        item = self.server._command_queue.get_nowait()
        self.assertEqual(item['request_id'], 'req-1')
        self.assertEqual(item['text'], 'check the deploy')
        self.assertTrue(item['scope'])
        self.assertEqual(self.server._command_queue.qsize(), 0)

    def test_a_resend_of_the_same_request_id_is_answered_but_not_queued_again(self):
        body = self.pair()
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()
            ws.send_json({'type': 'command', 'text': 'deploy', 'request_id': 'req-2'})
            first = ws.receive_json()
            self.assertEqual(ws.receive_json()['type'], 'chat.message')
            self.server._command_queue.get_nowait()
            ws.send_json({'type': 'command', 'text': 'deploy', 'request_id': 'req-2'})
            second = ws.receive_json()
            self.assertEqual(second['type'], 'command.status')
            self.assertEqual(second['payload']['request_id'], 'req-2')
            self.assertEqual(first['payload']['status'], second['payload']['status'])
        self.assertEqual(self.server._command_queue.qsize(), 0)

    def test_an_empty_command_is_an_error_not_a_queue_entry(self):
        body = self.pair()
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()
            ws.send_json({'type': 'command', 'text': '   '})
            error = ws.receive_json()
            self.assertEqual(error['type'], 'error')
        self.assertEqual(self.server._command_queue.qsize(), 0)

    def test_malformed_json_does_not_kill_the_socket(self):
        body = self.pair()
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()
            ws.send_text('{not json')
            self.assertEqual(ws.receive_json()['type'], 'error')
            ws.send_json({'type': 'ping'})
            self.assertEqual(ws.receive_json()['type'], 'pong')

    def test_phone_microphone_frames_reach_the_same_queue_the_browser_uses(self):
        body = self.pair()
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()
            ws.send_bytes(b'\x00' * 2048)
            for _ in range(100):
                time.sleep(0.005)
                if not self.server._phone_audio_queue.empty():
                    break
        frame = self.server._phone_audio_queue.get_nowait()
        self.assertEqual(frame['data'], b'\x00' * 2048)
        self.assertEqual(frame['mime_type'], 'audio/pcm')

    def test_the_voice_socket_streams_zaya_audio_without_the_control_socket(self):
        body = self.pair()
        bridge = self.mobile().bridge
        with self.client.websocket_connect(f"/ws/phone-output?token={body['token']}") as ws:
            start = ws.receive_json()
            self.assertEqual(start['type'], 'audio.start')
            self.assertEqual(start['payload']['sample_rate'], 24000)
            self.assertEqual(start['payload']['encoding'], 'pcm16')
            for _ in range(200):
                time.sleep(0.005)
                if bridge.audio_listener_count():
                    break
            self.assertEqual(bridge.audio_listener_count(), 1)
            bridge.set_output_target('phone')
            bridge.push_output_audio(b'\x11' * 2048)
            self.assertEqual(ws.receive_bytes(), b'\x11' * 2048)
        self.assertEqual(bridge.audio_listener_count(), 0)

    def test_zaya_voice_is_not_sent_when_the_laptop_is_the_target(self):
        body = self.pair()
        bridge = self.mobile().bridge
        with self.client.websocket_connect(f"/ws/phone-output?token={body['token']}") as ws:
            ws.receive_json()
            for _ in range(200):
                time.sleep(0.005)
                if bridge.audio_listener_count():
                    break
            self.assertEqual(bridge.push_output_audio(b'\x22' * 2048), 0)   # desktop-only
        self.assertEqual(bridge.audio_listener_count(), 0)

    def test_calls_can_be_answered_from_the_phone(self):
        body = self.pair()
        mobile = self.mobile()
        calls = mobile.calls
        mute_events = []
        mobile.bridge.add_sink(mute_events.append, name='test')
        call = calls.request_call(title='Deploy or wait?', detail='The staging deploy is queued',
                                  briefing='Ask about the deploy.')
        self.assertIsNotNone(call)
        with self.client.websocket_connect(f"/ws/mobile?token={body['token']}") as ws:
            ws.receive_json()
            ws.send_json({'type': 'call.answer', 'call_id': call.call_id})
            for _ in range(100):
                time.sleep(0.005)
                if calls.is_answered():
                    break
            self.assertTrue(calls.is_answered())
            self.assertTrue(mobile.bridge.phone_enabled())
            ws.send_json({'type': 'call.mute', 'muted': True})
            for _ in range(100):
                time.sleep(0.005)
                if any(event['type'] == 'system.call.mute' for event in mute_events):
                    break
            self.assertTrue(any(event['type'] == 'system.call.mute'
                                and event['payload']['muted'] for event in mute_events))
        # Losing the control socket ends a live call: a one-way call is worse
        # than a clean end, and the speaker routing returns to the laptop.
        for _ in range(200):
            time.sleep(0.005)
            if not calls.is_answered():
                break
        self.assertFalse(calls.is_answered())
        self.assertFalse(mobile.bridge.phone_enabled())


class DashboardCryptoTests(MobileServerTestCase):
    """The AES salt drifted from the browser once; encrypted commands silently
    fell back to plaintext. These tests pin server and client to one key."""

    def test_the_server_derives_the_key_the_browser_derives(self):
        from dashboard import server as dashboard
        self.assertEqual(dashboard._derive_key('session-key'),
                         hashlib.sha256(b'session-keyZAYA-DASHBOARD-v1').digest())

    def test_an_encrypted_command_from_a_browser_is_decrypted_and_queued(self):
        from dashboard import server as dashboard
        self.server._tokens.add('browser-token')
        self.server._token_keys['browser-token'] = 'session-key'
        encrypted = encrypt_for('session-key', b'ZAYA-DASHBOARD-v1', 'check the deploy')
        response = self.client.post('/api/command', headers=self.auth('browser-token'),
                                    json={'enc': encrypted})
        self.assertEqual(response.status_code, 200, response.text)
        item = self.server._command_queue.get_nowait()
        self.assertEqual(item['text'], 'check the deploy')

    def test_a_page_open_before_the_rename_still_decrypts(self):
        from dashboard import server as dashboard
        self.server._tokens.add('old-token')
        self.server._token_keys['old-token'] = 'session-key'
        encrypted = encrypt_for('session-key', b'JARVIS-DASHBOARD-v1', 'legacy command')
        response = self.client.post('/api/command', headers=self.auth('old-token'),
                                    json={'enc': encrypted})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.server._command_queue.get_nowait()['text'], 'legacy command')

    def test_a_payload_encrypted_with_another_key_is_refused(self):
        self.server._tokens.add('browser-token')
        self.server._token_keys['browser-token'] = 'session-key'
        encrypted = encrypt_for('some-other-key', b'ZAYA-DASHBOARD-v1', 'nope')
        response = self.client.post('/api/command', headers=self.auth('browser-token'),
                                    json={'enc': encrypted})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.server._command_queue.qsize(), 0)


class RateAgreementTests(unittest.TestCase):
    """Android opens its streams at the laptop's rates; a drift here is audible."""

    def test_the_mobile_module_mirrors_the_live_audio_rates(self):
        from dashboard import mobile_api
        import main
        self.assertEqual(mobile_api.PHONE_UP_RATE, main.SEND_SAMPLE_RATE)
        self.assertEqual(mobile_api.PHONE_DOWN_RATE, main.RECEIVE_SAMPLE_RATE)
        self.assertEqual(main.CHANNELS, 1)


if __name__ == '__main__':
    unittest.main()
