"""Voice continuity while a media/tool response remains open; no real devices."""
import asyncio
from collections import deque
from contextlib import suppress
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

from core.echo import EchoGuard, band_energies
from main import JarvisLive


def agent():
    live = JarvisLive.__new__(JarvisLive)
    live.ui = Mock(muted=False)
    live._audio_ducker = Mock()
    live._wake_enabled = False
    live._awake = True
    live._wake_detector = Mock()
    live._speaking_lock = threading.Lock()
    live._is_speaking = False
    live._companion_audio_active = False
    live._companion_tail_until = live._tail_until = 0
    live._ptt_enabled = live._ptt_held = live._phone_active = False
    live._out_latency = .2
    live._play_cursor = 0
    live._echo = EchoGuard()
    live._barge_audio = deque(maxlen=12)
    live._interrupted = False
    live._visemes = Mock()
    live.out_queue = asyncio.Queue(maxsize=16)
    live.audio_in_queue = asyncio.Queue()
    live._turn_done_event = asyncio.Event()
    live._begin_owner_goal = Mock()
    return live


class ListeningTests(unittest.IsolatedAsyncioTestCase):
    async def test_column_microphone_and_flat_playback_have_same_echo_fingerprint(self):
        pcm = (1500 * np.sin(2 * np.pi * 600 * np.arange(1024) / 16000)).astype(np.int16)
        np.testing.assert_array_equal(band_energies(pcm, 16000), band_energies(pcm.reshape(-1, 1), 16000))

    async def test_interruption_retains_first_words_and_stops_queued_voice(self):
        live = agent()
        live._is_speaking = True
        live._echo = Mock(required_blocks=5)
        live._echo.is_user_speech.return_value = True
        live.audio_in_queue.put_nowait(b'old response')
        blocks = [np.full((1024, 1), 2000 + i, dtype=np.int16) for i in range(5)]
        for block in blocks[:4]:
            live._microphone_input(block, asyncio.get_running_loop())
        self.assertTrue(live.out_queue.empty())
        self.assertTrue(live._is_speaking)
        live._microphone_input(blocks[4], asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertFalse(live._is_speaking)
        self.assertTrue(live.audio_in_queue.empty())
        self.assertEqual([live.out_queue.get_nowait()['data'] for _ in range(5)],
                         [b.tobytes() for b in blocks])

    async def test_echo_and_isolated_noise_cannot_interrupt(self):
        live = agent()
        live._is_speaking = True
        live._echo = Mock(required_blocks=5)
        live._echo.is_user_speech.side_effect = [False] * 20 + [True] * 4 + [False] + [True] * 4
        for _ in range(29):
            live._microphone_input(np.ones((1024, 1), dtype=np.int16), asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertTrue(live._is_speaking)
        self.assertTrue(live.out_queue.empty())

    async def test_real_echo_guard_rejects_output_but_allows_distinct_sustained_voice(self):
        live = agent()
        live._is_speaking = True
        phase = np.arange(1024) / 16000
        output = (1500 * np.sin(2 * np.pi * 600 * phase)).astype(np.int16).reshape(-1, 1)
        owner = (1500 * np.sin(2 * np.pi * 2600 * phase)).astype(np.int16).reshape(-1, 1)
        live._echo.note_output(output, 16000, .5)
        for _ in range(24):
            live._microphone_input(output, asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertTrue(live.out_queue.empty())
        for _ in range(live._echo.required_blocks):
            live._microphone_input(owner, asyncio.get_running_loop())
        await asyncio.sleep(0)
        self.assertFalse(live.out_queue.empty())
        self.assertFalse(live._is_speaking)

    async def test_mute_sleep_phone_ptt_and_poke_keep_privacy_gates(self):
        for flag in ('muted', 'sleep', '_phone_active', '_ptt_enabled', '_companion_audio_active'):
            live = agent()
            live._is_speaking = True
            live._echo = Mock(required_blocks=1)
            live._echo.is_user_speech.return_value = True
            if flag == 'muted':
                live.ui.muted = True
            elif flag == 'sleep':
                live._wake_enabled, live._awake = True, False
            else:
                setattr(live, flag, True)
            live._microphone_input(np.ones((1024, 1), dtype=np.int16), asyncio.get_running_loop())
            await asyncio.sleep(0)
            self.assertTrue(live.out_queue.empty(), flag)
            self.assertTrue(live._is_speaking, flag)

    async def test_congestion_drops_old_audio_and_preserves_latest_command(self):
        live = agent()
        loop = asyncio.get_running_loop()
        for i in range(20):
            live._microphone_input(np.full((1024, 1), i, dtype=np.int16), loop)
        await asyncio.sleep(0)
        self.assertEqual(live.out_queue.qsize(), 16)
        self.assertEqual([np.frombuffer(live.out_queue.get_nowait()['data'], dtype=np.int16)[0]
                          for _ in range(16)], list(range(4, 20)))

    async def test_closed_session_callback_cannot_feed_replacement(self):
        live = agent()
        live._microphone_input(np.ones((1024, 1), dtype=np.int16), asyncio.get_running_loop())
        live.out_queue = asyncio.Queue(maxsize=16)
        await asyncio.sleep(0)
        self.assertTrue(live.out_queue.empty())

    async def test_audio_drain_reopens_mic_without_server_turn_complete(self):
        live = agent()
        live.audio_in_queue.put_nowait(bytes(2400))
        stream = Mock(latency=.05)
        with patch('main.sd.RawOutputStream', return_value=stream), \
                patch('main.audio_devices.resolve', return_value=None):
            task = asyncio.create_task(live._play_audio())
            try:
                await asyncio.sleep(.6)
                stream.write.assert_called_once()
                self.assertFalse(live._turn_done_event.is_set())
                self.assertFalse(live._is_speaking)
                voice = (1500 * np.sin(2 * np.pi * 2600 * np.arange(1024) / 16000)).astype(np.int16)
                live._microphone_input(voice.reshape(-1, 1), asyncio.get_running_loop())
                await asyncio.sleep(0)
                self.assertFalse(live.out_queue.empty())
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

        stream.close.assert_called_once()

    async def test_output_failure_propagates_to_session_recovery(self):
        live = agent()
        live.audio_in_queue.put_nowait(bytes(2400))
        stream = Mock(latency=.05)
        stream.write.side_effect = RuntimeError('device disconnected')
        with patch('main.sd.RawOutputStream', return_value=stream), \
                patch('main.audio_devices.resolve', return_value=None):
            with self.assertRaisesRegex(RuntimeError, 'device disconnected'):
                await asyncio.wait_for(live._play_audio(), 2)
        self.assertFalse(live._is_speaking)
        stream.close.assert_called_once()

    async def test_server_interruption_discards_old_sound_and_accepts_next_answer(self):
        live = agent()
        live.audio_in_queue.put_nowait(b'stale voice')
        live._is_speaking = True

        async def responses():
            yield SimpleNamespace(server_content=SimpleNamespace(interrupted=True))
            yield SimpleNamespace(server_content=None, data=b'new answer', tool_call=None)
            await asyncio.Event().wait()

        live.session = SimpleNamespace(receive=responses)
        task = asyncio.create_task(live._receive_audio())
        try:
            await asyncio.sleep(0)
            self.assertFalse(live._interrupted)
            self.assertFalse(live._is_speaking)
            self.assertEqual(live.audio_in_queue.get_nowait(), b'new answer')
            self.assertTrue(live.audio_in_queue.empty())
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class MicrophoneStartupTests(unittest.TestCase):
    def test_working_microphone_with_slow_windows_startup_is_not_hidden(self):
        from core import audio_devices
        timer = None

        def input_stream(**kwargs):
            nonlocal timer
            # A real input stream on this machine starts after the old 350 ms
            # deadline. Simulate it without opening a user's device in tests.
            timer = threading.Timer(.45, lambda: kwargs['callback'](None, 2048, None, None))
            return Mock(start=timer.start, stop=timer.cancel, close=timer.cancel)

        with patch('sounddevice.InputStream', side_effect=input_stream), \
                patch.object(audio_devices, '_probe_results', {}):
            self.assertTrue(audio_devices._transport_works(0, 'input', ('fixture', 'input')))
        timer.join()
