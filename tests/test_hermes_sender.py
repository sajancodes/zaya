import subprocess
import unittest
from unittest.mock import Mock
from services.whatsapp.hermes_adapter import HermesAdapter
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'


class SenderTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.runner = Mock(return_value=subprocess.CompletedProcess([], 0, '{"success":true,"message_id":"sent-1"}', ''))
        self.adapter = HermesAdapter(self.store, ['hermes-native', 'send'], self.runner)

    def tearDown(self):
        self.store.db.close()

    def test_send_confirmed_once_and_shell_free(self):
        message = 'hello & "quoted" | text'
        self.assertEqual(self.adapter.send(CHAT, message, 'id').status, 'success')
        self.assertEqual(self.adapter.send(CHAT, message, 'id').status, 'success')
        self.assertEqual(self.runner.call_count, 1)
        self.assertEqual(self.runner.call_args.kwargs['input'], message)
        self.assertNotIn(message, self.runner.call_args.args[0])

    def test_failure_and_unknown_never_become_success(self):
        self.runner.return_value = subprocess.CompletedProcess([], 1, '{"error":"disconnected"}', '')
        self.assertEqual(self.adapter.send(CHAT, 'hello', 'failed').status, 'failed')
        self.runner.side_effect = subprocess.TimeoutExpired('hermes', 60)
        self.assertEqual(self.adapter.send(CHAT, 'hello', 'timeout').status, 'partial')
        self.assertEqual(self.adapter.send(CHAT, 'hello', 'timeout').status, 'partial')
        self.assertEqual(self.runner.call_count, 2)

    def test_attachment_directives_blocked(self):
        self.assertEqual(self.adapter.send(CHAT, 'MEDIA:../../private.txt', 'bad').status, 'failed')
        self.runner.assert_not_called()
