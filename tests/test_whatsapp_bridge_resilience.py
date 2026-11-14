import unittest
import threading
import time
import sqlite3
from unittest.mock import MagicMock
from services.whatsapp.native_bridge import NativeBridge

class NativeBridgeResilienceTests(unittest.TestCase):
    def test_callback_exception_does_not_kill_poll_loop(self):
        # Setup mock native bridge
        events_delivered = []
        def flaky_callback(msg):
            events_delivered.append(msg)
            if len(events_delivered) == 1:
                raise sqlite3.OperationalError('database is locked')

        bridge = NativeBridge(
            callback=flaky_callback,
            connection={'hermes_home': '.', 'session_path': '.', 'account_id': 'owner@s.whatsapp.net'}
        )
        bridge.process = MagicMock()
        bridge.process.poll.return_value = None

        # Mock http responses: health ok, messages returns 2 events
        mock_response_health = MagicMock()
        mock_response_health.json.return_value = {'status': 'connected'}
        mock_response_health.raise_for_status.return_value = None

        event1 = {'messageId': 'ev1', 'chatId': '123@s.whatsapp.net', 'body': 'Hello', 'timestamp': 100}
        event2 = {'messageId': 'ev2', 'chatId': '123@s.whatsapp.net', 'body': 'World', 'timestamp': 101}
        mock_response_messages = MagicMock()
        mock_response_messages.json.return_value = [event1, event2]
        mock_response_messages.raise_for_status.return_value = None

        call_count = 0
        def fake_get(url, **kwargs):
            nonlocal call_count
            if url.endswith('/health'):
                return mock_response_health
            if url.endswith('/messages'):
                call_count += 1
                if call_count == 1:
                    return mock_response_messages
                # After first batch, close bridge so thread terminates cleanly
                bridge.closed.set()
                mock_empty = MagicMock()
                mock_empty.json.return_value = []
                return mock_empty
            raise ValueError(f'Unexpected URL {url}')

        bridge.http.get = fake_get
        # Run _poll directly in a thread
        t = threading.Thread(target=bridge._poll)
        t.start()
        t.join(timeout=3)

        # Both events processed despite first event raising OperationalError
        self.assertEqual(len(events_delivered), 2)
        self.assertEqual(events_delivered[0].message_id, 'ev1')
        self.assertEqual(events_delivered[1].message_id, 'ev2')
        # Error from the first callback was captured and preserved
        self.assertIn('database is locked', str(bridge.error))
        # Thread finished cleanly and reset ready
        self.assertFalse(bridge.ready)

if __name__ == '__main__':
    unittest.main()
