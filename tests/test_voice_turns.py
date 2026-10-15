import asyncio
from contextlib import suppress
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.voice_turns import VoiceTurns
from tests.test_live_listening import agent


class VoiceTurnTests(unittest.TestCase):
    def test_retains_first_syllables_and_ends_despite_continuous_mic_packets(self):
        detector = Mock()
        detector.feed.side_effect = [False, False, True, True, False, False, False, False, True]
        turns = VoiceTurns(detector, silence_seconds=.9)
        self.assertEqual(turns.feed(b'prefix-1', 0), ([], False))
        self.assertEqual(turns.feed(b'prefix-2', .1), ([], False))
        self.assertEqual(turns.feed(b'first-word', .2), ([b'prefix-1', b'prefix-2', b'first-word'], False))
        self.assertEqual(turns.feed(b'last-word', .3), ([b'last-word'], False))
        self.assertFalse(turns.feed(b'brief-pause', .8)[1])
        self.assertTrue(turns.feed(b'quiet', 1.3)[1])
        self.assertFalse(turns.active)
        self.assertEqual(turns.feed(b'idle-1', 1.4), ([], False))
        self.assertEqual(turns.feed(b'idle-2', 1.5), ([], False))
        self.assertEqual(turns.feed(b'next-request', 1.6), ([b'idle-1', b'idle-2', b'next-request'], False))

    def test_idle_noise_does_not_create_a_turn(self):
        turns = VoiceTurns(Mock(feed=Mock(return_value=False)))
        for index in range(50):
            self.assertEqual(turns.feed(b'noise', index / 10), ([], False))
        self.assertFalse(turns.active)
        self.assertEqual(len(turns.prefix), 6)


class VoiceSenderTurnTests(unittest.IsolatedAsyncioTestCase):
    async def test_continuous_capture_sends_one_end_marker_then_can_accept_next_request(self):
        live = agent()
        live._turn_input_enabled = True
        live.session = SimpleNamespace(send_realtime_input=AsyncMock())
        turns = Mock(active=False)
        def feed(_pcm, _now):
            chunks, ended = next(packets)
            turns.active = bool(chunks) and not ended
            return chunks, ended
        packets = iter([([b'question'], False), ([b'quiet'], True), ([], False), ([b'next-question'], False)])
        turns.feed.side_effect = feed
        with patch('core.voice_turns.VoiceTurns', return_value=turns):
            task = asyncio.create_task(live._send_realtime())
            try:
                for _ in range(3):
                    live.out_queue.put_nowait({'data': b'fixture'})
                for _ in range(20):
                    await asyncio.sleep(0)
                calls = live.session.send_realtime_input.call_args_list
                self.assertEqual(sum('activity_end' in call.kwargs for call in calls), 1)
                self.assertEqual(sum('activity_start' in call.kwargs for call in calls), 1)
                self.assertFalse(any('audio_stream_end' in call.kwargs for call in calls))
                self.assertEqual([call.kwargs['audio'].data for call in calls if 'audio' in call.kwargs], [b'question', b'quiet'])
                live.out_queue.put_nowait({'data': b'fixture'})
                for _ in range(10):
                    await asyncio.sleep(0)
                self.assertEqual(live.session.send_realtime_input.call_args.kwargs['audio'].data, b'next-question')
                self.assertEqual(sum('activity_start' in call.kwargs for call in live.session.send_realtime_input.call_args_list), 2)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
