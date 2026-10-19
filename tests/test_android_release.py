import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.prepare_android_release import prepare


class AndroidReleaseTests(unittest.TestCase):
    def test_artifacts_contain_only_apk_and_safe_update_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apk, metadata = root / 'signed.apk', root / 'output-metadata.json'
            apk.write_bytes(b'fixture signed APK')
            metadata.write_text(json.dumps({'elements': [{'versionCode': 10001, 'versionName': '0.4.1'}]}))
            result = prepare(apk, metadata, root / 'public')
            self.assertEqual(result['sha256'], hashlib.sha256(apk.read_bytes()).hexdigest())
            self.assertEqual(result['version_code'], 10001)
            self.assertEqual((root / 'public/Zaya-Companion.apk').read_bytes(), apk.read_bytes())
            self.assertEqual(set(path.name for path in (root / 'public').iterdir()),
                             {'Zaya-Companion.apk', 'update.json', 'notes.md'})
            self.assertEqual(json.loads((root / 'public/update.json').read_text()), result)

    def test_invalid_version_does_not_create_a_release(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            apk, metadata = root / 'signed.apk', root / 'output-metadata.json'
            apk.write_bytes(b'fixture')
            metadata.write_text(json.dumps({'elements': [{'versionCode': 0, 'versionName': '0.4.1'}]}))
            with self.assertRaises(ValueError):
                prepare(apk, metadata, root / 'public')
            self.assertFalse((root / 'public').exists())
