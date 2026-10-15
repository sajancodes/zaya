"""Quiet owner-delegated replies, future chats, takeover and real tool routing."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from actions.whatsapp import whatsapp
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, trust_context
from core.proactive_manager import ProactiveManager
from core.tool_result import ToolResult
from services.whatsapp.handler import ReplyWorker
from services.whatsapp.models import Message
from services.whatsapp.service import WhatsAppService
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'
FUTURE = '456@s.whatsapp.net'
GROUP = '789@g.us'


class AutoModeTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.service = WhatsAppService(self.store)
        self.service.start = Mock()
        self.service.native_bridge = Mock(ready=True)
        self.store.ingest(Message('old', CHAT, CHAT, 'Earlier hello', 1, source='native_bridge'))
        self.adapter = Mock()
        self.adapter.send.return_value = ToolResult('success', 'accepted')
        self.worker = ReplyWorker(self.store, self.adapter,
                                  lambda *_: {'score': 10, 'needs_owner': False},
                                  lambda *_: {'reply': 'Hello! How can I help?', 'needs_owner': False})
        self.manager = ProactiveManager(self.store)

    def tearDown(self):
        self.worker.close()
        self.manager.close()
        self.store.db.close()

    def command(self, action, **kwargs):
        with patch('actions.whatsapp.get_service', return_value=self.service):
            return whatsapp({'action': action, **kwargs})

    def incoming(self, ident, chat=CHAT):
        message = Message(ident, chat, chat, 'Hello Zaya', 2, source='native_bridge')
        self.store.ingest(message)
        return message

    def test_global_voice_tool_enables_future_direct_chats_and_quiet_assistant_reply(self):
        result = self.command('start_auto')
        self.assertEqual(result.status, 'success')
        self.assertEqual(self.store.global_mode(), 'auto')
        self.assertEqual(self.store.chat(CHAT)['mode'], 'auto')
        self.adapter.send.assert_not_called()  # No history is replayed.
        message = self.incoming('new', FUTURE)
        self.worker.process(message)
        self.worker.process(message)
        self.adapter.send.assert_called_once()
        args = self.adapter.send.call_args.args
        self.assertEqual(args[0], FUTURE)
        self.assertIn('Zaya · Sajan Rai’s AI assistant:', args[1])
        self.assertIsNone(self.manager.next())
        self.assertEqual(self.store.chat(FUTURE)['mode'], 'auto')

    def test_global_auto_excludes_groups_and_paused_chats(self):
        self.incoming('group', GROUP)
        self.store.set_mode(CHAT, 'paused')
        self.command('start_auto')
        self.assertEqual(self.store.chat(GROUP)['mode'], 'observe')
        self.assertEqual(self.store.chat(CHAT)['mode'], 'paused')
        for message in (self.incoming('group-later', GROUP), self.incoming('paused-later')):
            self.worker.process(message)
        self.adapter.send.assert_not_called()

    def test_stop_auto_announces_only_new_messages_not_auto_backlog(self):
        self.command('start_auto')
        self.incoming('quiet')
        self.assertEqual(self.command('stop_auto').status, 'success')
        self.assertIsNone(self.manager.next())
        self.incoming('observe')
        item = self.manager.next()
        self.assertEqual(item['ids'], ['observe'])
        self.worker.process(self.incoming('new-after-stop', FUTURE))
        self.adapter.send.assert_not_called()
        self.assertEqual(self.store.chat(FUTURE)['mode'], 'observe')

    def test_manual_owner_reply_takes_over_even_with_global_auto_enabled(self):
        self.command('start_auto')
        self.store.ingest(Message('owner', CHAT, 'owner', 'I will handle this', 3, direction='outgoing', source='native_bridge'))
        self.worker.process(self.incoming('after-owner'))
        self.assertEqual(self.store.chat(CHAT)['mode'], 'manual')
        self.adapter.send.assert_not_called()

    def test_stop_auto_during_generation_prevents_transport_send(self):
        self.command('start_auto')
        def generate(*_):
            self.command('stop_auto')
            return {'reply': 'Hello', 'needs_owner': False}
        # The owner's concurrent command runs in its own trust context.
        def generate_in_owner_context(*_):
            import contextvars
            return contextvars.Context().run(generate)
        self.worker.generator = generate_in_owner_context
        self.worker.process(self.incoming('in-flight'))
        self.adapter.send.assert_not_called()

    def test_exact_chat_auto_does_not_enable_other_chats(self):
        self.command('start_auto', chat=CHAT)
        self.assertEqual(self.store.global_mode(), 'observe')
        self.worker.process(self.incoming('other', FUTURE))
        self.adapter.send.assert_not_called()

    def test_offline_mode_reports_partial_and_external_contact_cannot_enable_it(self):
        self.service.native_bridge = None
        result = self.command('start_auto')
        self.assertEqual(result.status, 'partial')
        self.assertIn('offline', result.summary)
        token = trust_context.set(TRUST_EXTERNAL_MESSAGE)
        try:
            with self.assertRaises(PermissionError):
                self.command('start_auto')
        finally:
            trust_context.reset(token)

    def test_global_mode_survives_restart_without_replaying_history(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'inbox.db'
            first = WhatsAppStore(path)
            first.set_global_mode('auto')
            first.db.close()
            second = WhatsAppStore(path)
            try:
                second.ingest(Message('fresh', FUTURE, FUTURE, 'Hello', 1))
                self.assertEqual(second.chat(FUTURE)['mode'], 'auto')
                self.assertIsNotNone(second.conversation(FUTURE)[0]['notified_at'])
            finally:
                second.db.close()
