import unittest
from unittest.mock import MagicMock
from services.whatsapp.service import WhatsAppService
from services.whatsapp.store import WhatsAppStore

class SendRequestIdUniquenessTests(unittest.TestCase):
    def test_repeated_message_gets_distinct_request_ids_when_unspecified(self):
        store = WhatsAppStore(':memory:')
        store.db.execute("INSERT INTO wa_chats (chat_id, title) VALUES ('target@s.whatsapp.net', 'Target Contact')")

        sent_requests = []
        fake_adapter = MagicMock()
        def fake_send(chat_id, message, request_id):
            sent_requests.append(request_id)
            result = MagicMock()
            result.status = 'success'
            return result
        fake_adapter.send = fake_send
        fake_adapter.command = ['mock']
        fake_adapter.transport = None

        service = WhatsAppService(store, fake_adapter)

        # Send "ok" twice without passing request_id
        service.send('target@s.whatsapp.net', 'ok')
        service.send('target@s.whatsapp.net', 'ok')

        self.assertEqual(len(sent_requests), 2)
        # Verify both requests were unique and neither was suppressed
        self.assertNotEqual(sent_requests[0], sent_requests[1])
        self.assertTrue(sent_requests[0].startswith('wa_'))
        self.assertTrue(sent_requests[1].startswith('wa_'))

if __name__ == '__main__':
    unittest.main()
