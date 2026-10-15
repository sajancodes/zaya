import asyncio
from contextlib import suppress
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock

import numpy as np
from tests.test_live_listening import agent


class OwnerPriorityTests(unittest.IsolatedAsyncioTestCase):
    def live(self):
        live = agent()
        live._owner_turn_pending = False
        live._owner_request_pending = False
        live._owner_epoch = 0
        live._notification_active = False
        live._last_user_speech = time.monotonic() - 30
        return live

    async def test_pending_owner_request_blocks_notices_even_after_three_seconds(self):
        live = self.live()
        self.assertFalse(live._notifications_busy())
        live._owner_turn_pending = True
        live._owner_request_pending = True
        self.assertTrue(live._notifications_busy())

    async def test_unanswered_voice_reconnects_but_active_tools_and_new_server_progress_do_not(self):
        live = self.live()
        live._owner_turn_pending = True
        live._owner_request_pending = True
        live._owner_turn_started = 100
        live._last_user_speech = 100
        live._voice_health = {'received_at': 101}
        self.assertTrue(live._voice_reply_stalled(125))
        live._tools_active = 1
        self.assertFalse(live._voice_reply_stalled(125))
        live._tools_active = 0
        live._voice_health['received_at'] = 120
        self.assertFalse(live._voice_reply_stalled(125))
        live._voice_health['received_at'] = 101
        live._last_tool_end = 120
        self.assertFalse(live._voice_reply_stalled(125))

    async def test_stall_keeps_the_session_and_task_instead_of_restarting(self):
        live = self.live()
        live.session = object()
        original = live.session
        live._operator_scope = 'same-request'
        live._owner_request_pending = True
        live._recover_stalled_voice()
        self.assertIs(live.session, original)
        self.assertEqual(live._operator_scope, 'same-request')
        self.assertFalse(live._owner_request_pending)
        self.assertFalse(live._owner_turn_pending)
        live._owner_turn_pending = True
        self.assertFalse(live._voice_reply_stalled(10000))

    async def test_local_noise_is_not_a_confirmed_unanswered_request(self):
        live = self.live()
        live._owner_turn_pending = True
        live._owner_turn_started = 100
        live._last_user_speech = 100
        self.assertFalse(live._voice_reply_stalled(200))

    async def test_local_speech_blocks_notice_before_server_transcribes_it(self):
        live = self.live()
        live._owner_detector = Mock()
        live._owner_detector.feed.return_value = True
        epoch = live._owner_epoch
        live._microphone_input(np.full((1024, 1), 2000, dtype=np.int16), asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertTrue(live._owner_turn_pending)
        self.assertFalse(live._can_announce(epoch))
        live._audio_ducker.microphone.assert_called_once()
        self.assertFalse(live.out_queue.empty())

    async def test_owner_speech_during_notification_synthesis_prevents_announcement(self):
        live = self.live()
        epoch = live._owner_epoch
        self.assertTrue(live._can_announce(epoch))
        live._owner_activity()
        # No server transcript or operator-scope change is needed.
        self.assertFalse(live._can_announce(epoch))

    async def test_interrupting_local_notice_does_not_suppress_main_model_reply(self):
        live = self.live()
        live._notification_active = True
        live._is_speaking = True
        live.audio_in_queue.put_nowait(b'notification voice')
        live.interrupt()
        self.assertFalse(live._interrupted)
        self.assertFalse(live._notification_active)
        self.assertTrue(live.audio_in_queue.empty())

        async def responses():
            yield SimpleNamespace(server_content=None, data=b'owner answer', tool_call=None)
            await asyncio.Event().wait()

        live.session = SimpleNamespace(receive=responses)
        task = asyncio.create_task(live._receive_audio())
        try:
            await asyncio.sleep(0)
            self.assertEqual(live.audio_in_queue.get_nowait(), b'owner answer')
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def test_response_audio_replaces_playing_notification(self):
        live = self.live()
        live._notification_active = True
        live.audio_in_queue.put_nowait(b'old notice')

        async def responses():
            yield SimpleNamespace(server_content=None, data=b'new response', tool_call=None)
            await asyncio.Event().wait()

        live.session = SimpleNamespace(receive=responses)
        task = asyncio.create_task(live._receive_audio())
        try:
            await asyncio.sleep(0)
            self.assertEqual(live.audio_in_queue.get_nowait(), b'new response')
            self.assertTrue(live.audio_in_queue.empty())
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    async def test_stream_pause_sends_one_end_marker_and_audio_can_resume(self):
        live = self.live()
        live.session = SimpleNamespace(send_realtime_input=AsyncMock())
        live.out_queue.put_nowait({'data': bytes(2048), 'mime_type': 'audio/pcm'})
        task = asyncio.create_task(live._send_realtime())
        try:
            await asyncio.sleep(1.3)
            calls = live.session.send_realtime_input.call_args_list
            self.assertEqual(len(calls), 12)
            self.assertEqual(calls[0].kwargs['audio'].mime_type, 'audio/pcm;rate=16000')
            self.assertTrue(all(call.kwargs['audio'].data == bytes(3200) for call in calls[1:11]))
            self.assertEqual(calls[-1].kwargs, {'audio_stream_end': True})
            await asyncio.sleep(.55)
            self.assertEqual(live.session.send_realtime_input.call_count, 12)
            live.out_queue.put_nowait({'data': bytes(2048)})
            await asyncio.sleep(.05)
            self.assertIn('audio', live.session.send_realtime_input.call_args.kwargs)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
