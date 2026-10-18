"""Conversation decisions through the real worker and a synthetic transport."""
import json
import subprocess
import threading
import unittest
from unittest.mock import Mock, patch

from core.proactive_manager import ProactiveManager
from services.whatsapp.handler import ReplyWorker
from services.whatsapp.hermes_adapter import HermesAdapter
from services.whatsapp.models import Message
from services.whatsapp.policy import generate_reply
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'
OTHER = '456@s.whatsapp.net'


class ConversationReplyTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()
        self.store.set_global_mode('auto')
        self.transport = Mock()
        self.sent = []
        def send(chat, text, quoted):
            self.sent.append((chat, text, quoted))
            return subprocess.CompletedProcess([], 0, json.dumps({
                'success': True, 'message_id': f'out-{len(self.sent)}'}))
        self.transport.send.side_effect = send
        self.adapter = HermesAdapter(self.store, transport=self.transport)
        self.generator = Mock(return_value={'reply': 'He is listening to music.', 'needs_owner': False})
        self.worker = ReplyWorker(self.store, self.adapter,
                                  lambda *_: {'score': 10, 'needs_owner': False},
                                  self.generator, quiet_seconds=0.03)

    def tearDown(self):
        self.worker.close()
        self.worker.pool.shutdown(wait=True, cancel_futures=True)
        self.store.db.close()

    def incoming(self, ident, text, chat=CHAT, **kwargs):
        # Equal timestamps are common for burst messages in native events.
        message = Message(ident, chat, chat, text, 1, source='native_bridge', **kwargs)
        self.store.ingest(message)
        return message

    def drain(self):
        with self.worker._condition:
            self.assertTrue(self.worker._condition.wait_for(lambda: not self.worker._pending, timeout=5))

    def test_burst_is_one_chronological_response_without_unnecessary_quote(self):
        for ident, text in [('one', 'Hi'), ('two', 'What is Sajan doing?'), ('three', 'Is he listening to music?')]:
            self.worker.enqueue(self.incoming(ident, text))
        self.drain()
        self.generator.assert_called_once()
        message, context = self.generator.call_args.args
        self.assertEqual(message.message_id, 'three')
        self.assertEqual([row['message_id'] for row in context], ['one', 'two', 'three'])
        self.assertTrue(all(row['pending_reply'] for row in context))
        self.assertEqual(len(self.sent), 1)
        self.assertIsNone(self.sent[0][2])
        self.assertEqual(len(self.store.rows('SELECT * FROM wa_messages WHERE handled=1')), 3)
        # Replayed native events cannot trigger another answer.
        self.worker.process(message)
        self.assertEqual(len(self.sent), 1)

    def test_thanks_can_end_conversation_without_reply_or_owner_alert(self):
        self.generator.return_value = {'reply': '', 'needs_owner': False, 'should_reply': False}
        message = self.incoming('thanks', 'Okay thanks, that is all')
        self.worker.process(message)
        self.worker.process(message)
        self.generator.assert_called_once()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.rows('SELECT * FROM wa_alerts'), [])

    def test_specific_earlier_question_can_be_quoted_in_same_chat(self):
        self.incoming('question', 'What project is he doing?')
        message = self.incoming('extra', 'Also hello Zaya')
        self.generator.return_value = {'reply': 'He is working on Zaya.', 'needs_owner': False,
                                       'should_reply': True, 'reply_to_id': 'question'}
        self.worker.process(message)
        self.assertEqual(self.sent[0][2], 'question')
        outgoing = self.store.rows("SELECT * FROM wa_messages WHERE direction='outgoing'")[0]
        self.assertEqual(outgoing['reply_to_id'], 'question')

    def test_cross_chat_or_invented_reply_target_is_rejected(self):
        self.incoming('private-other', 'Other conversation', OTHER)
        self.generator.return_value = {'reply': 'Hello', 'needs_owner': False, 'reply_to_id': 'private-other'}
        self.worker.process(self.incoming('here', 'Hello'))
        self.assertEqual(self.sent, [])
        self.assertIn('this chat context', self.store.rows('SELECT reason FROM wa_alerts')[0]['reason'])
        self.assertNotIn('private-other', str(self.generator.call_args.args[1]))

    def test_arrival_during_generation_reconsiders_entire_burst(self):
        entered, release = threading.Event(), threading.Event()
        contexts = []
        def generate(message, context):
            contexts.append([row['message_id'] for row in context if row.get('pending_reply')])
            if len(contexts) == 1:
                entered.set()
                if not release.wait(3):
                    raise RuntimeError('Test release timed out')
            return {'reply': 'One answer for the corrected question.', 'needs_owner': False}
        self.worker.generator = generate
        self.worker.enqueue(self.incoming('first', 'Is he working?'))
        try:
            self.assertTrue(entered.wait(3))
            self.worker.enqueue(self.incoming('correction', 'Sorry, I mean what music is playing?'))
        finally:
            release.set()
        self.drain()
        self.assertEqual(contexts, [['first'], ['first', 'correction']])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('corrected', self.sent[0][1])

    def test_batch_retains_urgent_owner_notification_without_commitment(self):
        self.worker.classifier = lambda message, _: (
            {'score': 90, 'needs_owner': True, 'notify_owner': True, 'reason': message.text}
            if message.message_id == 'urgent' else {'score': 10, 'needs_owner': False})
        self.generator.return_value = {'reply': '', 'needs_owner': False, 'should_reply': False}
        self.worker.enqueue(self.incoming('hello', 'Hello'))
        self.worker.enqueue(self.incoming('urgent', 'Urgent: ask Sajan to call now'))
        self.drain()
        manager = ProactiveManager(self.store)
        try:
            notice = manager.next()
            self.assertEqual(notice['kind'], 'relay')
            self.assertIn('call now', notice['announcement'])
            self.assertEqual(self.sent, [])
        finally:
            manager.close()

    def test_owner_reply_during_batch_generation_stops_send(self):
        def generate(*_):
            self.store.ingest(Message('manual', CHAT, 'owner', 'I am here', 2, direction='outgoing'))
            return {'reply': 'He is busy.', 'needs_owner': False}
        self.worker.generator = generate
        self.worker.enqueue(self.incoming('question', 'Is he around?'))
        self.drain()
        self.assertEqual(self.sent, [])
        self.assertEqual(self.store.chat(CHAT)['mode'], 'manual')

    def test_held_owner_decision_cannot_become_reply_target_via_harmless_message(self):
        self.worker.classifier = lambda message, _: (
            {'score': 90, 'needs_owner': True, 'notify_owner': True}
            if message.message_id == 'payment' else {'score': 10, 'needs_owner': False})
        self.generator.return_value = {'reply': 'Approved.', 'needs_owner': False, 'reply_to_id': 'payment'}
        self.worker.enqueue(self.incoming('payment', 'Can Sajan approve this payment?'))
        self.worker.enqueue(self.incoming('greeting', 'Hello Zaya'))
        self.drain()
        self.assertEqual(self.sent, [])

    def test_close_cancels_waiting_burst(self):
        self.worker.quiet_seconds = 30
        self.worker.enqueue(self.incoming('waiting', 'Hi'))
        self.worker.close()
        self.worker.pool.shutdown(wait=True, cancel_futures=True)
        self.generator.assert_not_called()
        self.assertEqual(self.sent, [])

    def test_policy_window_has_bounded_chronological_context_and_reply_links(self):
        context = [{'message_id': str(index), 'direction': 'incoming', 'text': 'x' * 10000,
                    'reply_to_id': str(index - 1), 'pending_reply': index >= 78} for index in range(80)]
        message = self.incoming('current', 'What about that project?')
        with patch('core.gemini.as_json', return_value={'reply': '', 'needs_owner': False, 'should_reply': False}) as model:
            generate_reply(message, context)
        payload = json.loads(model.call_args.args[0])
        rows = payload['conversation']
        self.assertEqual([row['message_id'] for row in rows], [str(i) for i in range(20, 80)])
        self.assertLessEqual(sum(len(row['text']) for row in rows), 16000)
        self.assertEqual(rows[-1]['reply_to_id'], '78')
        self.assertTrue(rows[-1]['pending_reply'])
        self.assertEqual(model.call_args.kwargs['config'].tools, [])
        instruction = model.call_args.kwargs['config'].system_instruction
        self.assertIn('should_reply false', instruction)
        self.assertIn('shared_current_activity', instruction)


if __name__ == '__main__':
    unittest.main()
