import json
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from core.proactive_manager import ProactiveManager
from core.tool_result import ToolResult
from services.whatsapp.bridge import HookReceiver
from services.whatsapp.bridge_read_state import ANCHOR, POLL_ANCHOR, instrument, prepare_bridge
from services.whatsapp.models import Message
from services.whatsapp.native_bridge import NativeBridge
from services.whatsapp.service import WhatsAppService
from services.whatsapp.store import WhatsAppStore

CHAT = '123@s.whatsapp.net'


class ReadStateTests(unittest.TestCase):
    def setUp(self):
        self.store = WhatsAppStore()

    def tearDown(self):
        self.store.db.close()

    def incoming(self, mid, timestamp):
        self.store.ingest(Message(mid, CHAT, CHAT, mid, timestamp))

    def test_manual_reply_clears_only_older_messages_and_notices(self):
        self.incoming('old', 10)
        self.incoming('later', 30)
        self.store.ingest(Message('reply', CHAT, 'owner', 'answer', 20, direction='outgoing'))
        self.incoming('delayed-old', 15)
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 1)
        records = WhatsAppService(self.store).query('unread').data['records']
        self.assertEqual(records[0]['latest_unread_text'], 'later')
        manager = ProactiveManager(self.store)
        try:
            self.assertEqual(manager.next()['ids'], ['later'])
        finally:
            manager.close()

    def test_phone_read_event_and_stale_event_preserve_new_incoming(self):
        self.incoming('old', 10)
        self.store.sync_read_state({'chatId': CHAT, 'unreadCount': 0, 'timestamp': 20})
        self.incoming('new', 30)
        self.incoming('delayed-old', 12)
        self.store.sync_read_state({'chatId': CHAT, 'unreadCount': 0, 'timestamp': 15})
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 1)

    def test_read_message_cannot_gain_a_late_spoken_alert(self):
        self.incoming('read', 10)
        self.store.mark_read(CHAT, through=20)
        self.assertFalse(self.store.alert(Message('read', CHAT, CHAT, 'urgent', 10), 90, 'urgent', 'late result', True))

    def test_alias_merging_retains_read_watermark(self):
        alias = '456@lid'
        self.store.ingest(Message('old', alias, CHAT, 'old', 10))
        self.store.mark_read(alias, through=20)
        self.incoming('new', 30)
        self.store.link_alias(alias, CHAT)
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 1)
        self.assertEqual(self.store.chat(CHAT)['read_through'], 20)

    def test_explicit_send_does_not_consume_incoming_during_delivery(self):
        self.incoming('old', time.time() - 30)
        def send(*_args):
            self.incoming('new', time.time() + 1)
            return ToolResult('success', 'accepted')
        adapter = Mock(command=['fixture'], send=Mock(side_effect=send))
        result = WhatsAppService(self.store, adapter).send(CHAT, 'answer', 'test')
        self.assertEqual(result.status, 'success')
        self.assertEqual(self.store.chat(CHAT)['unread_count'], 1)

    def test_malformed_send_result_is_failed_without_resending(self):
        bridge = NativeBridge(Mock())
        bridge.ready = True
        bridge.http = Mock()
        bridge.http.post.return_value.json.side_effect = ValueError('not json')
        self.assertEqual(bridge.send(CHAT, 'hello').returncode, 1)
        bridge.http.post.assert_called_once()

    def test_unsupported_bridge_fails_without_rewriting_upstream(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bridge.js'
            path.write_text('unsupported', encoding='utf-8')
            with self.assertRaises(ValueError):
                prepare_bridge(path)
            self.assertEqual(path.read_text(), 'unsupported')

    @unittest.skipUnless(shutil.which('node'), 'Node runtime unavailable')
    def test_bridge_read_observations_never_send_receipts(self):
        source = """#!/usr/bin/env node
const handlers = {}, messageQueue = [], MAX_QUEUE_SIZE = 5;
const sock = {ev: {on: (name, handler) => handlers[name] = handler}};
// messageQueue.push(event)
""" + ANCHOR + "});\nfunction poll() { " + POLL_ANCHOR + " return msgs; }\n"
        source = instrument(source) + """
handlers['chats.update']([{id:'123@s.whatsapp.net',unreadCount:0}]);
handlers['messaging-history.set']({chats:[{id:'456@s.whatsapp.net',unreadCount:0,conversationTimestamp:10}]});
if (zayaReadStates.get('456@s.whatsapp.net').timestamp !== 10) throw Error('Historical read watermark changed');
messageQueue.push({body:'real incoming'});
for (let n=0; n<5000; n++) handlers['chats.update']([{id:`${n}@s.whatsapp.net`,unreadCount:0}]);
console.log(JSON.stringify({events:poll(),remaining:messageQueue.length}));
"""
        result = subprocess.run(['node', '-e', source], capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        self.assertEqual(data['events'][0], {'body': 'real incoming'})
        self.assertEqual(len(data['events']), 4097)
        self.assertTrue(all(event['event'] == 'chat.read_state' for event in data['events'][1:]))
        self.assertEqual(data['remaining'], 0)

    def test_hook_can_close_without_start(self):
        with tempfile.TemporaryDirectory() as folder:
            receiver = HookReceiver(Mock(), Path(folder) / 'descriptor.json')
            receiver.close()

