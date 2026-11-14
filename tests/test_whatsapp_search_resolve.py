import unittest
from services.whatsapp.store import WhatsAppStore
from services.whatsapp.service import WhatsAppService
from services.whatsapp.models import Message

class WhatsAppSearchResolveTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore(':memory:')
        self.service = WhatsAppService(self.store)

        # Seed sample chats
        self.store.db.executescript('''
            INSERT INTO wa_chats (chat_id, title, last_message_at, unread_count)
            VALUES
                ('101@s.whatsapp.net', 'Subash Rai', 1000.0, 0),
                ('102@s.whatsapp.net', 'Shubh Das', 1010.0, 0),
                ('103@s.whatsapp.net', 'Project Alpha', 1020.0, 0);
        ''')

        # Seed sample messages
        self.store.ingest(Message('m1', '101@s.whatsapp.net', '101@s.whatsapp.net', 'Here is 100% discount on shoes', 1000.0))
        self.store.ingest(Message('m2', '102@s.whatsapp.net', '102@s.whatsapp.net', 'Status is _pending_review_', 1010.0))
        self.store.ingest(Message('m3', '103@s.whatsapp.net', '103@s.whatsapp.net', 'Subash please check the build', 1020.0))

    def tearDown(self):
        self.store.db.close()

    def test_search_matches_chat_title_and_message_text(self):
        # Matches by contact title
        res = self.service.query('search', query='Shubh')
        self.assertEqual(res.status, 'partial')
        self.assertGreaterEqual(len(res.data['records']), 1)
        self.assertEqual(res.data['records'][0]['chat_id'], '102@s.whatsapp.net')

        # Matches by message text
        res = self.service.query('search', query='shoes')
        self.assertEqual(res.status, 'partial')
        self.assertEqual(len(res.data['records']), 1)
        self.assertEqual(res.data['records'][0]['chat_id'], '101@s.whatsapp.net')

    def test_search_escapes_sql_wildcards(self):
        # Searching for literal %
        res_pct = self.service.query('search', query='%')
        self.assertEqual(res_pct.status, 'partial')
        self.assertEqual(len(res_pct.data['records']), 1)
        self.assertEqual(res_pct.data['records'][0]['message_id'], 'm1')

        # Searching for literal _
        res_underscore = self.service.query('search', query='_')
        self.assertEqual(res_underscore.status, 'partial')
        self.assertEqual(len(res_underscore.data['records']), 1)
        self.assertEqual(res_underscore.data['records'][0]['message_id'], 'm2')

    def test_search_respects_chat_parameter(self):
        # Query 'Subash' matches both 101 (title) and 103 (message text mentions Subash)
        res_all = self.service.query('search', query='Subash')
        self.assertEqual(len(res_all.data['records']), 2)

        # Scoped to 101 only
        res_chat = self.service.query('search', chat='101@s.whatsapp.net', query='Subash')
        self.assertEqual(len(res_chat.data['records']), 1)
        self.assertEqual(res_chat.data['records'][0]['chat_id'], '101@s.whatsapp.net')

    def test_resolve_chat_exact_prefix_substring_fuzzy(self):
        # 1. Exact case-insensitive
        self.assertEqual(self.service.resolve_chat('subash rai'), '101@s.whatsapp.net')
        self.assertEqual(self.service.resolve_chat('Subash Rai'), '101@s.whatsapp.net')

        # 2. Prefix match
        self.assertEqual(self.service.resolve_chat('Subash'), '101@s.whatsapp.net')
        self.assertEqual(self.service.resolve_chat('Shubh'), '102@s.whatsapp.net')

        # 3. Substring match
        self.assertEqual(self.service.resolve_chat('Rai'), '101@s.whatsapp.net')
        self.assertEqual(self.service.resolve_chat('Alpha'), '103@s.whatsapp.net')

        # 4. Light fuzzy match
        self.assertEqual(self.service.resolve_chat('Subhash'), '101@s.whatsapp.net')

    def test_resolve_chat_ambiguous_and_unknown_errors(self):
        # Add duplicate prefix
        self.store.db.execute("INSERT INTO wa_chats (chat_id, title) VALUES ('104@s.whatsapp.net', 'Subash Sharma')")

        # Now 'Subash' is ambiguous
        with self.assertRaises(ValueError) as ctx:
            self.service.resolve_chat('Subash')
        self.assertIn('Ambiguous contact', str(ctx.exception))
        self.assertIn('Subash Rai', str(ctx.exception))
        self.assertIn('Subash Sharma', str(ctx.exception))

        # Unknown name provides suggestions or clean error
        with self.assertRaises(ValueError) as ctx:
            self.service.resolve_chat('Zebra')
        self.assertIn('No chat matches "Zebra"', str(ctx.exception))

if __name__ == '__main__':
    unittest.main()
