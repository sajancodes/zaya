import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from services.whatsapp.native_bridge import NativeBridge, verified_orphan
from services.whatsapp.store import WhatsAppStore
from services.whatsapp.models import Message
from services.whatsapp.service import WhatsAppService


class RecoveryTests(unittest.TestCase):
    def test_orphan_requires_exact_session_script_port_and_dead_parent(self):
        bridge, session = Path('bridge.js'), Path('session')
        process = Mock()
        process.cmdline.return_value = ['node', str(bridge), '--session', str(session), '--port', '8768']
        process.parent.return_value = None
        process.pid = 42
        connection = SimpleNamespace(pid=42, status='LISTEN', laddr=SimpleNamespace(port=8768))
        with patch('psutil.net_connections', return_value=[connection]), patch('psutil.Process', return_value=process):
            self.assertEqual(verified_orphan(8768, bridge, session).pid, 42)
            with self.assertRaises(RuntimeError):
                verified_orphan(8768, bridge, Path('different-session'))
            process.parent.return_value = Mock()
            process.parent.return_value.create_time.return_value = 1
            process.create_time.return_value = 2
            with self.assertRaises(RuntimeError):
                verified_orphan(8768, bridge, session)

    def test_only_one_monitor_can_lease_a_session(self):
        with tempfile.TemporaryDirectory() as folder:
            first = NativeBridge(Mock(), {'session_path': folder})
            second = NativeBridge(Mock(), {'session_path': folder})
            first._claim()
            try:
                with self.assertRaises(RuntimeError):
                    second._claim()
            finally:
                first.close()
            second._claim()
            second.close()

    def test_dead_bridge_is_replaced_and_transport_rebound(self):
        store = WhatsAppStore()
        service = WhatsAppService(store)
        old, new = Mock(), Mock()
        old.process.poll.return_value = 1
        service.native_bridge = old
        try:
            with patch('services.whatsapp.connection.load_connection', return_value={'paired': True}), patch('services.whatsapp.native_bridge.NativeBridge', return_value=new):
                service.connect_live()
            old.close.assert_called_once()
            new.start.assert_called_once()
            self.assertIs(service.adapter.transport, new)
        finally:
            store.db.close()

    def test_offline_queries_are_stale_and_send_is_not_submitted(self):
        store = WhatsAppStore()
        adapter = Mock()
        service = WhatsAppService(store, adapter)
        service.receiver = Mock()
        store.ingest(Message('test', '123@s.whatsapp.net', '123@s.whatsapp.net', 'hello', 1))
        try:
            result = service.query('recent')
            self.assertEqual(result.status, 'partial')
            self.assertFalse(result.data['live_connected'])
            with patch.object(service, 'connect_live'):
                result = service.send('123@s.whatsapp.net', 'reply', 'request')
            self.assertEqual(result.data['transport_status'], 'not_submitted')
            adapter.send.assert_not_called()
            self.assertEqual(store.rows('SELECT * FROM wa_send_intents'), [])
        finally:
            store.db.close()

    def test_legacy_whatsapp_send_tool_directs_to_stateful_tool(self):
        from actions.send_message import send_message
        with patch('actions.send_message._send_whatsapp') as legacy:
            result = send_message({'platform': 'whatsapp', 'receiver': 'Friend', 'message_text': 'hello'})
            self.assertEqual(result.status, 'failed')
            self.assertIn('whatsapp tool', result.summary)
            legacy.assert_not_called()
