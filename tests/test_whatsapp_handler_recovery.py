import unittest
import time
import sqlite3
from unittest.mock import MagicMock
from services.whatsapp.models import Message
from services.whatsapp.handler import ReplyWorker

class ReplyWorkerDrainRecoveryTests(unittest.TestCase):
    def test_transient_sqlite_error_and_drain_cleanup(self):
        # Mock store with transient sqlite operational error on rows
        store = MagicMock()
        store.canonical_chat.side_effect = lambda cid: cid

        call_count = 0
        def flaky_rows(query, params=()):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise sqlite3.OperationalError('database is locked')
            return []

        store.rows.side_effect = flaky_rows
        adapter = MagicMock()

        worker = ReplyWorker(store, adapter, quiet_seconds=0.05)
        msg = Message('m_retry', 'chat_retry@s.whatsapp.net', 'sender', 'Hello', 100.0)

        # Enqueue should start drain
        worker.enqueue(msg)

        # Wait for worker drain to finish
        time.sleep(0.5)

        # Drain must clean up pending and release slot
        self.assertNotIn('chat_retry@s.whatsapp.net', worker._pending)
        self.assertEqual(worker.slots._value, 50)
        worker.close()

if __name__ == '__main__':
    unittest.main()
