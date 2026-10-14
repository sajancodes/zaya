import unittest
from services.whatsapp.models import Message, normalize_hook
from services.whatsapp.store import WhatsAppStore

CHAT = '123456789@s.whatsapp.net'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.message = Message('one', CHAT, 'contact', 'hello', 1)

    def tearDown(self):
        self.store.db.close()

    def test_dedup_and_unread(self):
        self.assertTrue(self.store.ingest(self.message))
        self.assertFalse(self.store.ingest(self.message))
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 1)
        self.store.mark_read(CHAT)
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 0)

    def test_modes_manual_outgoing_and_idempotency(self):
        self.store.ingest(self.message)
        self.store.set_mode(CHAT, 'auto')
        self.store.ingest(Message('out', CHAT, 'owner', 'I will answer', 2, direction='outgoing'))
        self.assertEqual(self.store.chat(CHAT)['mode'], 'manual')
        self.assertTrue(self.store.claim_message('one'))
        self.assertFalse(self.store.claim_message('one'))
        self.assertTrue(self.store.reserve_send('request', CHAT, 'reply'))
        self.assertFalse(self.store.reserve_send('request', CHAT, 'reply'))

    def test_alert_dedup(self):
        self.store.ingest(self.message)
        self.assertTrue(self.store.alert(self.message, 90, 'urgent', 'deadline'))
        self.assertFalse(self.store.alert(self.message, 90, 'urgent', 'deadline'))

    def test_hook_is_partial_and_deterministic(self):
        ctx = {'platform': 'whatsapp', 'chat_id': CHAT, 'user_id': 'user', 'message': 'hello', 'session_id': 'session'}
        a, b = normalize_hook('agent:start', ctx), normalize_hook('agent:start', ctx)
        self.assertEqual(a.message_id, b.message_id)
        self.assertFalse(a.complete)
        self.assertIsNone(normalize_hook('agent:start', {**ctx, 'platform': 'telegram'}))

    def test_path_injection_rejected(self):
        with self.assertRaises(ValueError):
            Message('id', '../../secret', 'sender', 'text', 1)
