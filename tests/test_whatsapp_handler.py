import unittest
from unittest.mock import Mock
from services.whatsapp.models import Message
from services.whatsapp.store import WhatsAppStore
from services.whatsapp.handler import ReplyWorker
from core.tool_result import ToolResult
from actions.terminal_exec import terminal_exec

CHAT = '123@s.whatsapp.net'


class HandlerTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.message = Message('raw-1', CHAT, 'contact', 'Hello', 1, source='native_bridge')
        self.store.ingest(self.message)
        self.store.set_mode(CHAT, 'auto')
        self.adapter = Mock()
        self.adapter.send.return_value = ToolResult('success', 'accepted', evidence=[{'message_id': 'reply-1'}], side_effect=True)
        self.worker = ReplyWorker(self.store, self.adapter, lambda *_: {'score': 10, 'needs_owner': False}, lambda *_: {'reply': 'Hello!', 'needs_owner': False})

    def tearDown(self):
        self.worker.close()
        self.store.db.close()

    def test_duplicate_never_replies_twice(self):
        self.worker.process(self.message)
        self.worker.process(self.message)
        self.adapter.send.assert_called_once()

    def test_manual_takeover_during_generation(self):
        def generate(*_):
            self.store.ingest(Message('manual', CHAT, 'owner', 'I will reply', 2, direction='outgoing'))
            return {'reply': 'AI reply', 'needs_owner': False}
        self.worker.generator = generate
        self.worker.process(self.message)
        self.adapter.send.assert_not_called()
        self.assertEqual(self.store.chat(CHAT)['mode'], 'manual')

    def test_important_and_partial_input_are_held(self):
        self.worker.classifier = lambda *_: {'score': 90, 'needs_owner': True}
        self.worker.process(self.message)
        self.adapter.send.assert_not_called()
        self.worker.classifier = lambda *_: {'score': 1, 'needs_owner': False}
        self.worker.process(Message('hook', CHAT, 'contact', 'partial', 3, complete=False))
        self.adapter.send.assert_not_called()

    def test_external_injection_cannot_reach_terminal(self):
        def malicious(*_):
            terminal_exec({'command': 'git status'})
            return {'reply': 'done', 'needs_owner': False}
        self.worker.generator = malicious
        self.worker.process(self.message)
        self.adapter.send.assert_not_called()
        self.assertIn('no access', self.store.rows('SELECT reason FROM wa_alerts')[0]['reason'])
