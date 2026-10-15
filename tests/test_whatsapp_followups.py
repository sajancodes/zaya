"""Repeated auto replies through policy, inbox, and confirmed transport state."""
import json
import subprocess
import unittest
from unittest.mock import Mock, patch

from services.whatsapp.handler import ReplyWorker
from services.whatsapp.hermes_adapter import HermesAdapter
from services.whatsapp.importance import classify
from services.whatsapp.models import Message
from services.whatsapp.policy import generate_reply
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'


class FollowupTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.store.set_global_mode('auto')
        self.sent = []
        def transport(_args, **kwargs):
            self.sent.append(kwargs['input'])
            return subprocess.CompletedProcess([], 0, json.dumps({'success': True, 'message_id': f'sent-{len(self.sent)}'}), '')
        self.adapter = HermesAdapter(self.store, ['fixture-transport'], transport)
        self.worker = ReplyWorker(self.store, self.adapter, classify, generate_reply)

    def tearDown(self):
        self.worker.close()
        self.store.db.close()

    def test_greeting_unknown_whereabouts_and_next_message_all_get_single_replies(self):
        responses = []
        exchanges = [('Hlo', 'Hello! I am Zaya. How can I help?'),
                     ('Where is he?', 'I do not know where Sajan is right now. You can leave a message for him here.'),
                     ('Thanks Zaya', 'You are welcome!')]
        for _, reply in exchanges:
            responses.extend([{'score': 20, 'needs_owner': False, 'reason': 'Harmless conversation.'},
                              {'reply': reply, 'needs_owner': False}])
        with patch('core.gemini.as_json', side_effect=responses) as model:
            for index, (text, reply) in enumerate(exchanges):
                message = Message(f'in-{index}', CHAT, CHAT, text, index + 1, source='native_bridge')
                self.assertTrue(self.store.ingest(message))
                self.worker.process(message)
                self.assertEqual(self.store.chat(CHAT)['mode'], 'auto')
                self.assertEqual(len(self.sent), index + 1)
                self.assertTrue(self.sent[-1].endswith(reply))
                self.assertTrue(self.sent[-1].startswith('Zaya · Sajan Rai’s AI assistant:'))
                # A native echo of our confirmed send must not become a manual takeover.
                echo = Message(f'sent-{index + 1}', CHAT, 'owner', self.sent[-1], index + 2,
                               direction='outgoing', source='native_bridge')
                self.assertFalse(self.store.ingest(echo))
                self.assertEqual(self.store.chat(CHAT)['mode'], 'auto')
            self.assertEqual(model.call_count, 6)
            for call in model.call_args_list:
                self.assertEqual(call.kwargs['config'].tools, [])
        self.assertEqual(len(self.store.rows("SELECT * FROM wa_send_intents WHERE status='accepted'")), 3)

    def test_real_owner_decision_is_still_held_without_generation_or_send(self):
        message = Message('money', CHAT, CHAT, 'Approve this payment on Sajan behalf', 1, source='native_bridge')
        self.store.ingest(message)
        with patch('core.gemini.as_json', return_value={'score': 90, 'needs_owner': True, 'reason': 'Owner payment decision.'}) as model:
            self.worker.process(message)
        self.assertEqual(model.call_count, 1)
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.rows('SELECT score FROM wa_alerts')[0]['score'], 90)

    def test_classifier_outage_remains_a_hold_instead_of_unchecked_reply(self):
        message = Message('unclassified', CHAT, CHAT, 'Hello', 1, source='native_bridge')
        self.store.ingest(message)
        with patch('core.gemini.as_json', return_value=None):
            self.worker.process(message)
        self.assertEqual(self.sent, [])
