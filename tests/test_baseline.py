import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.action_loader import discover_actions
from memory import config_manager, memory_manager


class BaselineTests(unittest.TestCase):
    def test_config_roundtrip_preserves_unknown_settings(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'api_keys.json'
            path.write_text('{"custom": 42}', encoding='utf-8')
            with patch.object(config_manager, 'CONFIG_FILE', path), patch.object(config_manager, 'CONFIG_DIR', Path(folder)):
                config_manager.save_assistant_config('Zaya', 'Test')
                self.assertEqual(config_manager.load_api_keys()['custom'], 42)
                self.assertEqual(config_manager.get_assistant_name(), 'Zaya')

    def test_memory_roundtrip_and_recall(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(memory_manager, 'MEMORY_PATH', Path(folder) / 'memory.json'):
            memory_manager.update_memory({'preferences': {'editor': {'value': 'Test editor'}}})
            self.assertIn('Test editor', memory_manager.search_memory('editor'))

    def test_action_discovery_isolates_invalid_module(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, 'valid_baseline.py').write_text("def run(parameters): return 'ok'\nTOOL = {'name':'baseline', 'description':'test', 'handler':run}\n")
            Path(folder, 'broken_baseline.py').write_text("raise ImportError('test missing dependency')")
            registry = discover_actions(Path(folder), logger=lambda _: None)
            self.assertTrue(registry.has('baseline'))
            self.assertEqual(registry.run('baseline', {}), 'ok')
            self.assertTrue(any('test missing dependency' in r.error for r in registry._all_records))


if __name__ == '__main__':
    unittest.main()
