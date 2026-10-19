"""Settings updates preserve credentials on interruption and concurrent edits."""
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from memory import config_manager as config


class AtomicConfigTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / 'api_keys.json'
        mocked = patch.object(config, 'CONFIG_FILE', self.path)
        mocked.start()
        self.addCleanup(mocked.stop)
        self.path.write_text(json.dumps({'gemini_api_keys': ['fixture-key'], 'unrelated': 'preserve'}))

    def test_interrupted_replace_keeps_original_and_removes_temporary_file(self):
        before = self.path.read_bytes()
        with patch.object(config.os, 'replace', side_effect=OSError('simulated disk error')):
            with self.assertRaises(OSError):
                config.save_voice('Charon')
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.zaya-config-*.tmp')), [])

    def test_parallel_settings_updates_do_not_lose_keys_or_plugin_fields(self):
        with ThreadPoolExecutor(max_workers=8) as workers:
            list(workers.map(lambda index: config.save_plugin_config('fixture', {str(index): index}), range(40)))
        data = config.load_api_keys()
        self.assertEqual(data['plugin_config']['fixture'], {str(index): index for index in range(40)})
        self.assertEqual(data['gemini_api_keys'], ['fixture-key'])
        self.assertEqual(data['unrelated'], 'preserve')

    def test_corrupt_settings_are_not_silently_overwritten(self):
        self.path.write_text('{broken')
        with self.assertRaises(ValueError):
            config.save_brief_enabled(True)
        self.assertEqual(self.path.read_text(), '{broken')

    def test_plural_keys_are_configured_and_brief_persists_boolean(self):
        self.assertEqual(config.get_gemini_key(), 'fixture-key')
        config.save_brief_enabled(1)
        self.assertIs(config.load_api_keys()['morning_brief_enabled'], True)
