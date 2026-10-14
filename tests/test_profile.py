import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from memory import memory_manager
from memory.profile_bootstrap import bootstrap


class ProfileTests(unittest.TestCase):
    def test_explicit_local_import_has_provenance(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(memory_manager, 'MEMORY_PATH', Path(folder) / 'memory.json'):
            path = Path(folder) / 'input.json'
            path.write_text(json.dumps({'preferences': {'editor': 'Test editor'}}))
            result = bootstrap(path, Path(folder) / 'profile.json')
            self.assertEqual(result['fact_count'], 1)
            fact = memory_manager.load_memory()['preferences']['editor']
            self.assertEqual(fact['source'], 'user_profile_import')
            self.assertEqual(fact['confidence'], 1.0)
            self.assertIn('created_at', fact)

    def test_sensitive_seed_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'
            path.write_text('{"identity":{"password":"private"}}')
            with self.assertRaises(ValueError):
                bootstrap(path, Path(folder) / 'profile.json')
