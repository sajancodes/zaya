import json
import tempfile
import unittest
from pathlib import Path
from services.whatsapp.connection import load_connection
from services.whatsapp.native_bridge import normalize_event


class NativeBridgeTests(unittest.TestCase):
    def test_complete_message_and_manual_owner_event(self):
        event = {'messageId': 'stable-id', 'chatId': '123@s.whatsapp.net', 'senderId': 'contact', 'body': 'hello', 'timestamp': 123, 'chatName': 'Test'}
        message = normalize_event(event)
        self.assertTrue(message.complete)
        self.assertEqual(message.message_id, 'stable-id')
        self.assertEqual(normalize_event({**event, 'fromOwner': True}).direction, 'outgoing')

    def test_exact_session_identity_and_credential_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            session = home / 'whatsapp' / 'session'
            session.mkdir(parents=True)
            (session / 'creds.json').write_text(json.dumps({'me': {'id': '123:4@s.whatsapp.net'}, 'registered': True, 'secret': 'private'}))
            path = home / 'connection.json'
            path.write_text(json.dumps({'hermes_home': str(home), 'session_path': str(session), 'account_id': '123@s.whatsapp.net'}))
            record = load_connection(path)
            self.assertEqual(record['account_id'], '123@s.whatsapp.net')
            self.assertNotIn('secret', record)
            path.write_text(json.dumps({**record, 'account_id': '456@s.whatsapp.net'}))
            with self.assertRaises(ValueError):
                load_connection(path)
