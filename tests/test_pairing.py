import json
import tempfile
import unittest
from pathlib import Path
from services.whatsapp.pairing import PairingManager


class PairingTests(unittest.TestCase):
    def test_exact_session_saved_without_copying_device_keys(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder) / 'hermes'
            manager = PairingManager(home, Path(folder) / 'config' / 'hermes_connection.json')
            manager.session.mkdir(parents=True)
            (manager.session / 'creds.json').write_text(json.dumps({'me': {'id': '123:5@s.whatsapp.net'}, 'secretKey': 'private'}))
            manager._save_connection({'id': '123:5@s.whatsapp.net', 'name': 'Test'})
            self.assertTrue(manager.status()['paired'])
            record = json.loads(manager.config_path.read_text())
            self.assertEqual(record['account_id'], '123@s.whatsapp.net')
            self.assertNotIn('secretKey', record)
            self.assertEqual(Path(record['session_path']), manager.session.resolve())
            self.assertIn('WHATSAPP_ENABLED=true', (home / '.env').read_text())
