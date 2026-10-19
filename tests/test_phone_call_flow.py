"""Calls are phone conversations, not a stream of laptop room audio."""
import asyncio
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from core.mobile_bridge import MobileBridge
from core.mobile_calls import MobileCallManager, PhoneCallSettings
from core import presence
from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from dashboard.mobile_api import MobileApi
from tests.test_live_listening import agent


class Timer:
    def __init__(self, interval, fn, args=()):
        self.interval, self.fn, self.args = interval, fn, args
        self.cancelled = False
    def start(self):
        pass
    def cancel(self):
        self.cancelled = True
    def fire(self):
        self.fn(*self.args)  # A callback may already be dispatched at cancellation.


class PhoneCallFlowTests(unittest.TestCase):
    def setUp(self):
        self.bridge = MobileBridge()
        self.calls = MobileCallManager(self.bridge, clock=lambda: 1000)
        self.calls.set_reachable_provider(lambda: True)
        self.timer = patch('core.mobile_calls.threading.Timer', side_effect=Timer)
        self.timer.start()
        self.addCleanup(self.timer.stop)
        self.addCleanup(self.calls.stop)
        server = SimpleNamespace(_phone_audio_queue=asyncio.Queue(), device_registry=Mock(), _wake_callback=Mock())
        with patch('dashboard.mobile_api.get_bridge', return_value=self.bridge), \
                patch('dashboard.mobile_api.get_call_manager', return_value=self.calls):
            self.api = MobileApi(server)
        self.phone = SimpleNamespace(device={'device_id': 'phone-a'}, capabilities={}, dropped=0, enqueue=Mock())
        self.other = SimpleNamespace(device={'device_id': 'phone-b'}, capabilities={}, dropped=0, enqueue=Mock())

    def incoming(self):
        return self.calls.request_call(title='Zaya needs you', requested=True)

    def test_outgoing_rings_five_to_ten_seconds_then_answers(self):
        hook = Mock()
        self.calls.set_answer_hook(hook)
        self.api._call_control(self.phone, 'call.start', '', {})
        call = self.calls.active()
        timer = self.calls._answer_timer
        self.assertTrue(5 <= timer.interval <= 10)
        self.assertEqual(call.direction, 'outgoing')
        self.assertEqual(call.state, 'ringing')
        self.assertFalse(self.bridge.call_active)
        self.api._accept_phone_audio(self.phone, bytes(640))
        self.assertTrue(self.api.server._phone_audio_queue.empty())
        self.api._call_control(self.phone, 'call.answer', call.call_id, {})
        self.assertEqual(call.state, 'ringing')  # The owner cannot accidentally skip Zaya's delay.
        timer.fire()
        self.assertEqual(call.state, 'answered')
        self.assertTrue(self.bridge.call_active)
        hook.assert_called_once_with(call)

    def test_hangup_while_dialing_cannot_be_resurrected_by_late_answer(self):
        call = self.calls.dial('phone-a')
        timer = self.calls._answer_timer
        self.api._call_control(self.phone, 'call.end', call.call_id, {})
        self.assertTrue(timer.cancelled)
        timer.fire()
        self.assertIsNone(self.calls.active())
        self.assertFalse(self.bridge.call_active)

    def test_phone_audio_is_accepted_only_for_answered_owner_and_not_when_muted(self):
        self.api._accept_phone_audio(self.phone, bytes(640))
        call = self.incoming()
        self.api._accept_phone_audio(self.phone, bytes(640))
        self.assertTrue(self.api.server._phone_audio_queue.empty())
        self.api._call_control(self.phone, 'call.answer', call.call_id, {})
        self.api._accept_phone_audio(self.other, bytes(640))
        self.assertTrue(self.api.server._phone_audio_queue.empty())
        self.api._accept_phone_audio(self.phone, bytes(640))
        packet = self.api.server._phone_audio_queue.get_nowait()
        self.assertEqual(packet['call_id'], call.call_id)
        self.api._call_control(self.phone, 'call.mute', call.call_id, {'muted': True})
        self.api._accept_phone_audio(self.phone, bytes(640))
        self.assertTrue(self.api.server._phone_audio_queue.empty())
        self.api._call_control(self.phone, 'call.mute', call.call_id, {'muted': False})
        self.api._accept_phone_audio(self.phone, bytes(640))
        self.assertFalse(self.api.server._phone_audio_queue.empty())

    def test_other_device_cannot_end_call_or_change_output_to_laptop(self):
        call = self.incoming()
        self.calls.answer(call.call_id, device_id='phone-a')
        self.api._call_control(self.other, 'call.end', call.call_id, {})
        self.assertEqual(call.state, 'answered')
        self.assertEqual(self.bridge.set_output_target('both'), 'phone')
        self.assertFalse(self.bridge.desktop_enabled())
        self.api._call_control(self.phone, 'call.end', call.call_id, {})
        self.assertTrue(self.bridge.desktop_enabled())

    def test_explicit_test_calls_can_redial_but_automatic_alerts_keep_limits(self):
        call = self.incoming()
        self.calls.end(call.call_id)
        self.assertIsNone(self.calls.request_call(title='Automatic update'))
        self.assertIsNotNone(self.calls.request_call(title='Owner requested a test', requested=True))

    def test_explicit_call_rings_even_when_model_labels_it_important_or_normal(self):
        from actions.mobile_call import call_owner
        events = []
        with patch('actions.mobile_call.get_call_manager', return_value=self.calls), \
                patch.object(self.bridge, 'emit', side_effect=events.append):
            for urgency in ('important', 'normal'):
                result = call_owner({'reason': 'Owner requested a test', 'requested': True, 'urgency': urgency})
                self.assertEqual(result.data['delivery'], 'call')
                self.assertEqual(events[-1]['type'], 'call.incoming')
                self.assertEqual(self.calls.active().priority, 1)
                self.calls.end(self.calls.active().call_id)
            result = call_owner({'reason': 'Ordinary update', 'urgency': 'important'})
            self.assertEqual(result.data['delivery'], 'notification')

    def test_missed_call_attempts_keep_hourly_spam_cap_without_creating_ghost_calls(self):
        now = [1000.0]
        self.calls._clock = lambda: now[0]
        events = []
        with patch.object(self.bridge, 'emit', side_effect=events.append):
            for index in range(self.calls.max_per_hour):
                call = self.calls.request_call(title=f'Alert {index}')
                self.assertIsNotNone(call)
                self.calls.miss(call.call_id)
                now[0] += self.calls.min_interval + 1
            self.assertEqual(self.calls._blocked_reason('', now[0]), 'the hourly call limit is reached')
            count = len(self.calls._calls)
            self.assertIsNone(self.calls.request_call(title='One more automatic alert'))
        self.assertEqual(len(self.calls._calls), count)
        self.assertIsNone(self.calls.active())
        self.assertEqual(events[-1]['type'], 'system.notify')

    def test_unavailable_zaya_does_not_answer_and_stop_cancels_delayed_answer(self):
        call = self.calls.dial('phone-a')
        self.calls.set_available_provider(lambda: False)
        self.calls._answer_timer.fire()
        self.assertIsNone(self.calls.active())
        self.calls.set_available_provider(lambda: True)
        call = self.calls.dial('phone-a')
        timer = self.calls._answer_timer
        self.calls.stop()
        timer.fire()
        self.assertIsNone(self.calls.active())

    def test_work_done_while_declared_away_rings_but_status_queries_do_not(self):
        self.calls.set_away_provider(lambda: True)
        with patch('core.mobile_calls.phone_call_settings', return_value=PhoneCallSettings(quiet_from=None, quiet_to=None)):
            self.calls.handle_event({'event': 'task.updated', 'task': {
                'id': 'query', 'state': 'completed', 'source': 'local_desktop',
                'side_effects': [{'step': 'coding_job', 'summary': 'status'}]}})
            self.assertIsNone(self.calls.active())
            self.calls.handle_event({'event': 'task.updated', 'task': {
                'id': 'work', 'state': 'completed', 'source': 'coding_job', 'goal': 'Build the requested app'}})
        self.assertEqual(self.calls.active().title, 'Task finished')

    def test_urgent_message_rings_and_decline_keeps_microphone_closed(self):
        self.calls.handle_event({'event': 'whatsapp.alert.created', 'score': 90, 'reason': 'A time-sensitive message'})
        call = self.calls.active()
        self.assertEqual(call.source, 'whatsapp')
        self.api._call_control(self.phone, 'call.decline', call.call_id, {})
        self.assertFalse(self.bridge.call_active)
        self.assertIsNone(self.calls.answer(call.call_id))


class PhoneMicrophoneTests(unittest.IsolatedAsyncioTestCase):
    async def test_phone_call_silence_or_mute_never_returns_laptop_microphone(self):
        live = agent()
        live._bridge = MobileBridge()
        live._bridge.set_call_active(True)
        live._phone_active = False  # Even after the old one-second stream timeout.
        live._wake_enabled, live._awake = True, False
        live._microphone_input(np.ones(1024, dtype=np.int16), asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertTrue(live.out_queue.empty())
        live._wake_detector.feed.assert_not_called()
        live._bridge.set_call_active(False)
        live._wake_enabled, live._awake = False, True
        live._microphone_input(np.ones(1024, dtype=np.int16), asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertFalse(live.out_queue.empty())


class DeclaredPresenceTests(unittest.TestCase):
    def test_going_out_is_immediate_persisted_and_owner_only(self):
        with tempfile.TemporaryDirectory() as folder, patch('core.presence.PRESENCE_PATH', Path(folder) / 'presence.json'), \
                patch('core.presence.desktop_idle_seconds', return_value=0):
            presence.set_presence('away')
            self.assertTrue(presence.owner_is_away())
            self.assertEqual(presence.declared_presence()['mode'], 'away')
            with with_trust(TRUST_EXTERNAL_MESSAGE), self.assertRaises(PermissionError):
                presence.set_presence('present')
            presence.set_presence('present')
            self.assertFalse(presence.owner_is_away())
            presence.set_presence('auto')
            self.assertFalse(presence.owner_is_away())


if __name__ == '__main__':
    unittest.main()
