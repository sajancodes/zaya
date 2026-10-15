import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.proactive_manager import ProactiveManager
from core.tool_result import ToolResult
from services.whatsapp.handler import ReplyWorker
from services.whatsapp.importance import classify
from services.whatsapp.models import Message
from services.whatsapp.policy import generate_reply
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / 'inbox.db'
        self.store = WhatsAppStore(self.path)
        self.store.set_global_mode('auto')
        self.adapter = Mock()
        self.adapter.send.return_value = ToolResult('success', 'accepted')
        self.worker = ReplyWorker(self.store, self.adapter, classify, generate_reply)
        self.manager = ProactiveManager(self.store)

    def tearDown(self):
        self.manager.close()
        self.worker.close()
        self.store.db.close()
        self.folder.cleanup()

    def receive(self, text, classification, reply=None):
        message = Message('fixture-' + str(len(self.store.rows('SELECT * FROM wa_messages'))), CHAT, CHAT, text, 1,
                          display_name='Test contact', source='native_bridge')
        self.store.ingest(message)
        results = [classification]
        if reply:
            results.append({'reply': reply, 'needs_owner': False})
        with patch('core.gemini.as_json', side_effect=results) as model:
            self.worker.process(message)
            return model.call_args_list

    def test_ordinary_auto_chat_and_manual_takeover_are_silent(self):
        self.receive('Hello', {'score': 10, 'needs_owner': False, 'notify_owner': False}, 'Hello!')
        self.assertIsNone(self.manager.next())
        self.store.set_mode(CHAT, 'manual')
        self.receive('Are you there?', {'score': 10, 'needs_owner': False, 'notify_owner': False})
        self.assertIsNone(self.manager.next())
        self.adapter.send.assert_called_once()

    def test_pass_along_request_is_queued_before_acknowledgment_and_survives_restart(self):
        calls = self.receive('Please tell Sajan dinner is ready.',
                             {'score': 40, 'needs_owner': False, 'notify_owner': True}, 'Your message is queued for Sajan.')
        payload = json.loads(calls[-1].args[0])
        self.assertTrue(payload['owner_relay_queued'])
        self.assertTrue(self.store.rows('SELECT notify_owner FROM wa_alerts')[0]['notify_owner'])
        self.assertIsNone(self.manager.next(busy=True))
        reopened = WhatsAppStore(self.path)
        manager = ProactiveManager(reopened)
        try:
            item = manager.next()
            self.assertEqual(item['kind'], 'relay')
            self.assertIn('Test contact', item['announcement'])
            self.assertIn('dinner is ready', item['announcement'])
            manager.delivered(item)
            self.assertIsNone(self.manager.next())
        finally:
            manager.close()
            reopened.db.close()

    def test_urgent_owner_decision_is_spoken_without_automatic_commitment(self):
        self.receive('Urgent: please authorize the payment now.',
                     {'score': 90, 'needs_owner': True, 'notify_owner': True})
        self.adapter.send.assert_not_called()
        item = self.manager.next()
        self.assertEqual(item['kind'], 'relay')
        self.assertIn('authorize the payment', item['announcement'])

    def test_worker_failure_does_not_become_generic_auto_voice(self):
        self.worker.classifier = Mock(side_effect=RuntimeError('fixture failure'))
        message = Message('broken', CHAT, CHAT, 'Hi', 1, source='native_bridge')
        self.store.ingest(message)
        self.worker.process(message)
        self.assertTrue(self.store.rows('SELECT * FROM wa_alerts'))
        self.assertIsNone(self.manager.next())
