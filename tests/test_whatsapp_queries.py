import unittest
from services.whatsapp.models import Message
from services.whatsapp.store import WhatsAppStore
from services.whatsapp.service import WhatsAppService


class QueryTests(unittest.TestCase):
    def test_state_queries_and_ambiguous_contacts(self):
        store = WhatsAppStore()
        try:
            service = WhatsAppService(store)
            store.ingest(Message('one', '123@s.whatsapp.net', '123', 'hello', 1, display_name='Test'))
            self.assertEqual(service.resolve_chat('Test'), '123@s.whatsapp.net')
            self.assertEqual(len(service.query('unread').data['records']), 1)
            self.assertEqual(len(service.query('search', query='hello').data['records']), 1)
            self.assertFalse(service.query('status').data['full_inbox_available'])
            store.ingest(Message('two', '456@s.whatsapp.net', '456', 'hey', 2, display_name='Test'))
            with self.assertRaises(ValueError):
                service.resolve_chat('Test')
        finally:
            store.db.close()
