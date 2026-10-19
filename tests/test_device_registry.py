"""Paired devices are durable, hash-only records that survive a restart.

The bug this suite pins down: device sessions used to be a Python dict, so every
Zaya restart silently unpaired the phone and forced another QR scan.
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path

from core.device_registry import DeviceRegistry


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self._folder = tempfile.TemporaryDirectory()
        self.path = Path(self._folder.name) / 'runtime.db'
        self.registry = DeviceRegistry(self.path)

    def tearDown(self):
        try:
            self.registry.db.close()
        except Exception:
            pass
        self._folder.cleanup()

    # ── pairing ───────────────────────────────────────────────────────────────

    def test_secret_is_returned_once_and_never_written_to_disk(self):
        record, secret = self.registry.pair('Pixel 8', app_version='1.0', platform='android',
                                            ip='100.64.0.5')
        self.assertTrue(secret)
        self.assertEqual(record['device_name'], 'Pixel 8')
        self.assertEqual(record['platform'], 'android')
        self.assertEqual(record['last_ip'], '100.64.0.5')
        self.assertFalse(record['revoked'])
        self.assertNotIn('credential_hash', record)
        self.assertNotIn('session_key', record)

        raw = self.path.read_bytes()
        self.assertNotIn(secret.encode(), raw)          # the secret is not persisted
        row = self.registry.db.execute('SELECT credential_hash FROM paired_devices').fetchone()
        self.assertTrue(row['credential_hash'].startswith('pbkdf2_sha256$'))

    def test_a_restart_keeps_the_device_paired(self):
        record, secret = self.registry.pair('Pixel 8')
        reopened = DeviceRegistry(self.path)             # a fresh process, same DB
        try:
            self.assertIsNotNone(reopened.authenticate(record['device_id'], secret))
            self.assertEqual(reopened.get(record['device_id'])['device_name'], 'Pixel 8')
        finally:
            reopened.db.close()

    def test_migration_adds_columns_to_an_older_table(self):
        legacy = Path(self._folder.name) / 'legacy.db'
        connection = sqlite3.connect(legacy)
        connection.execute(
            'CREATE TABLE paired_devices (device_id TEXT PRIMARY KEY, device_name TEXT NOT NULL,'
            ' credential_hash TEXT NOT NULL, session_key TEXT NOT NULL DEFAULT "",'
            ' created_at REAL NOT NULL, last_seen REAL NOT NULL, revoked INTEGER NOT NULL DEFAULT 0,'
            ' app_version TEXT NOT NULL DEFAULT "", platform TEXT NOT NULL DEFAULT "")')
        connection.commit()
        connection.close()

        migrated = DeviceRegistry(legacy)
        try:
            columns = {row['name'] for row in migrated.db.execute('PRAGMA table_info(paired_devices)')}
            self.assertTrue({'last_ip', 'fail_count', 'fail_at'}.issubset(columns))
            record, secret = migrated.pair('Old phone', ip='10.0.0.2')
            self.assertIsNotNone(migrated.authenticate(record['device_id'], secret))
        finally:
            migrated.db.close()

    # ── authentication ────────────────────────────────────────────────────────

    def test_wrong_secret_unknown_device_and_revoked_device_all_fail(self):
        record, secret = self.registry.pair('Pixel 8')
        self.assertIsNone(self.registry.authenticate(record['device_id'], 'not-the-secret'))
        self.assertIsNone(self.registry.authenticate('no-such-device', secret))
        self.assertIsNone(self.registry.authenticate('', secret))
        self.assertTrue(self.registry.revoke(record['device_id']))
        self.assertIsNone(self.registry.authenticate(record['device_id'], secret))

    def test_five_failures_lock_the_device_until_the_window_passes(self):
        record, secret = self.registry.pair('Pixel 8')
        for _ in range(5):
            self.assertIsNone(self.registry.authenticate(record['device_id'], 'wrong'))
        self.assertGreater(self.registry.locked(record['device_id']), 0)
        # Even the correct secret is refused while the lockout stands.
        self.assertIsNone(self.registry.authenticate(record['device_id'], secret))

    def test_successful_login_clears_the_failure_counter(self):
        record, secret = self.registry.pair('Pixel 8')
        for _ in range(3):
            self.registry.authenticate(record['device_id'], 'wrong')
        self.assertIsNotNone(self.registry.authenticate(record['device_id'], secret))
        self.assertEqual(self.registry.locked(record['device_id']), 0.0)

    def test_session_key_is_released_only_after_authentication(self):
        record, _secret = self.registry.pair('Browser', session_key='sk-live', secret='browser-token')
        self.assertIsNone(self.registry.session_key_for(record['device_id'], 'wrong'))
        self.assertEqual(self.registry.session_key_for(record['device_id'], 'browser-token'), 'sk-live')

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def test_touch_records_where_and_what_the_device_is(self):
        record, _secret = self.registry.pair('Pixel 8')
        self.registry.touch(record['device_id'], app_version='2.1', platform='android-15',
                            ip='100.64.0.9')
        updated = self.registry.get(record['device_id'])
        self.assertEqual(updated['app_version'], '2.1')
        self.assertEqual(updated['platform'], 'android-15')
        self.assertEqual(updated['last_ip'], '100.64.0.9')
        self.assertGreaterEqual(updated['last_seen'], record['last_seen'])

    def test_revoked_devices_are_listed_only_when_asked_for(self):
        keep, _ = self.registry.pair('Keep')
        drop, _ = self.registry.pair('Drop')
        self.registry.revoke(drop['device_id'])
        visible = [device['device_id'] for device in self.registry.list()]
        self.assertIn(keep['device_id'], visible)
        self.assertNotIn(drop['device_id'], visible)
        everything = [device['device_id'] for device in self.registry.list(include_revoked=True)]
        self.assertIn(drop['device_id'], everything)

    def test_revoke_all_is_the_admin_escape_hatch(self):
        first, first_secret = self.registry.pair('One')
        second, second_secret = self.registry.pair('Two')
        self.assertEqual(self.registry.revoke_all(), 2)
        self.assertIsNone(self.registry.authenticate(first['device_id'], first_secret))
        self.assertIsNone(self.registry.authenticate(second['device_id'], second_secret))
        self.assertEqual(self.registry.list(), [])

    def test_forget_removes_the_row_entirely(self):
        record, _secret = self.registry.pair('Pixel 8')
        self.assertTrue(self.registry.forget(record['device_id']))
        self.assertIsNone(self.registry.get(record['device_id']))
        self.assertFalse(self.registry.forget(record['device_id']))


if __name__ == '__main__':
    unittest.main()
