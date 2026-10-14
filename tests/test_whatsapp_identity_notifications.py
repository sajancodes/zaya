import unittest
from unittest.mock import patch
from services.whatsapp.native_bridge import normalize_event
from services.whatsapp.models import Message
from services.whatsapp.store import WhatsAppStore
from services.whatsapp.service import WhatsAppService
from core.proactive_manager import ProactiveManager

PHONE, LINK, OWNER = '123@s.whatsapp.net', '456@lid', '999@s.whatsapp.net'


class IdentityNotificationTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()

    def tearDown(self):
        self.store.db.close()

    def test_owner_name_never_labels_peer_and_linked_reply_is_visible(self):
        outgoing = normalize_event(dict(messageId='out', chatId=LINK, senderId=PHONE,
                                        fromOwner=True, senderName='Owner', body='Hi', timestamp=1), OWNER)
        self.assertEqual(outgoing.sender_id, OWNER)
        self.store.ingest(outgoing)
        self.assertEqual(self.store.chat(PHONE)['title'], PHONE)
        incoming = normalize_event(dict(messageId='in', chatId=LINK, senderId=PHONE,
                                        senderName='Friend', body='Hello Zaya', timestamp=2), OWNER)
        self.store.ingest(incoming)
        service = WhatsAppService(self.store)
        self.assertEqual(service.resolve_chat('Friend'), PHONE)
        self.assertEqual(len(self.store.conversation(LINK)), 2)
        self.assertEqual(service.query('conversation', chat=PHONE).data['records'][0]['text'], 'Hello Zaya')
        self.store.identify_contact(PHONE, 'Verified Friend')
        self.store.ingest(Message('later', PHONE, PHONE, 'hi', 3, display_name='Spoofed Owner'))
        self.assertEqual(self.store.chat(PHONE)['title'], 'Verified Friend')

    def test_existing_split_chats_merge_without_losing_messages_or_unread(self):
        self.store.ingest(Message('lid', LINK, PHONE, 'reply', 2))
        self.store.ingest(Message('phone', PHONE, OWNER, 'sent', 1, direction='outgoing', ai_generated=True))
        self.store.link_alias(LINK, PHONE)
        self.assertEqual(len(self.store.rows('SELECT * FROM wa_chats')), 1)
        self.assertEqual(len(self.store.conversation(PHONE)), 2)
        self.assertEqual(self.store.chat(LINK)['unread_count'], 1)
        self.store.set_mode(LINK, 'auto')
        self.assertEqual(self.store.chat(PHONE)['mode'], 'auto')

    def test_normal_messages_notify_without_classifier_and_only_once(self):
        now = [1000.0]
        manager = ProactiveManager(self.store, lambda: now[0])
        try:
            self.store.ingest(Message('normal', PHONE, PHONE, 'Hello Zaya', 1, display_name='Friend'))
            self.assertIsNone(manager.next(busy=True))
            notice = manager.next()
            self.assertIn('Friend', notice['announcement'])
            self.assertIn('Hello Zaya', notice['announcement'])
            manager.delivered(notice)
            self.store.alert(Message('normal', PHONE, PHONE, 'Hello Zaya', 1), 80, 'urgent', 'late classification')
            now[0] += 10
            self.assertIsNone(manager.next())
        finally:
            manager.close()

    def test_screen_fallback_refuses_whatsapp_or_unspecified_platform(self):
        from plugins.chat_takeover import run
        with patch('plugins.chat_takeover._grab_screen') as screen:
            self.assertEqual(run({'action': 'start', 'platform': 'whatsapp'}).status, 'failed')
            self.assertEqual(run({'action': 'start'}).status, 'failed')
            screen.assert_not_called()
