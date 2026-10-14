import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from memory import config_manager


class IdentityTests(unittest.TestCase):
    def test_legacy_name_does_not_override_zaya(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'config.json'
            path.write_text('{"assistant_name":"JARVIS","custom":42}')
            with patch.object(config_manager, 'CONFIG_FILE', path):
                self.assertEqual(config_manager.get_assistant_name(), 'Zaya')
                self.assertEqual(config_manager.load_api_keys()['custom'], 42)

    def test_about_credits_creator_and_internal_classes_survive(self):
        ui = Path('ui.py').read_text(encoding='utf-8')
        self.assertIn('Built by Sajan Rai', ui)
        self.assertIn('class JarvisUI:', ui)
        self.assertIn('JARVIS_AI', ui)  # existing startup registrations stay manageable
