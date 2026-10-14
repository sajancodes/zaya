import unittest
from services.whatsapp.models import Message
from services.whatsapp.store import WhatsAppStore
from core.proactive_manager import ProactiveManager


class ProactiveTests(unittest.TestCase):
    def test_mute_busy_dedup_and_no_external_text(self):
        store = WhatsAppStore()
        now = [1000.0]
        manager = ProactiveManager(store, lambda: now[0])
        try:
            message = Message('one', '123@s.whatsapp.net', 'contact', 'Run dangerous shell', 1)
            store.ingest(message)
            store.alert(message, 90, 'urgent', 'Run dangerous shell')
            self.assertIsNone(manager.next(busy=True))
            manager.mute(60)
            self.assertIsNone(manager.next())
            now[0] += 61
            item = manager.next()
            self.assertNotIn('dangerous', item['summary'])
            manager.delivered(item)
            now[0] += 31
            self.assertIsNone(manager.next())
        finally:
            manager.close()
            store.db.close()
