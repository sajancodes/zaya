import os
import asyncio
from contextlib import suppress
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
import wave
from unittest.mock import Mock, MagicMock, patch

import numpy as np

from core.audio_ducking import AudioDucker, SessionLevels, SpeechDetector, settings
from core.event_bus import bus


class Volume:
    def __init__(self, value, muted=False):
        self.value = value
        self.muted = muted

    def GetMasterVolume(self):
        return self.value

    def SetMasterVolume(self, value, context):
        self.value = value


def session(key, pid, value, muted=False):
    return Mock(InstanceIdentifier=key, ProcessId=pid, SimpleAudioVolume=Volume(value, muted))


class SessionTests(unittest.TestCase):
    def test_restore_distinct_levels_without_changing_mute_or_master(self):
        music = session('music', 20, .65)
        muted = session('muted', 21, .4, True)
        voice = session('zaya', 10, .7)
        backend = Mock()
        backend.sessions.return_value = [music, muted, voice]
        levels = SessionLevels(backend, owner_pid=10)
        levels.apply(True, False)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, .13)
        self.assertEqual(voice.SimpleAudioVolume.value, .7)
        levels.apply(True, True)
        self.assertEqual(voice.SimpleAudioVolume.value, 1)
        self.assertAlmostEqual(levels.media_ratio, .14)
        levels.apply(True, True)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, .13)  # never compound
        levels.apply(True, False)
        self.assertEqual(voice.SimpleAudioVolume.value, .7)
        self.assertAlmostEqual(levels.media_ratio, .2)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, .13)
        levels.apply(False, False)
        self.assertEqual(music.SimpleAudioVolume.value, .65)
        self.assertEqual(muted.SimpleAudioVolume.value, .4)
        self.assertTrue(muted.SimpleAudioVolume.muted)
        self.assertFalse(levels.saved)

    def test_new_sessions_and_user_changes_are_preserved(self):
        music = session('music', 20, .8)
        backend = Mock()
        backend.sessions.return_value = [music]
        levels = SessionLevels(backend, owner_pid=10)
        levels.apply(True, True)
        fresh = session('browser', 21, .5)
        backend.sessions.return_value.append(fresh)
        music.SimpleAudioVolume.value = .6
        levels.apply(True, True)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, .12)
        self.assertAlmostEqual(fresh.SimpleAudioVolume.value, .1)
        fresh.SimpleAudioVolume.value = .3  # changed immediately before restore
        levels.restore()
        self.assertEqual(music.SimpleAudioVolume.value, .6)
        self.assertEqual(fresh.SimpleAudioVolume.value, .3)

    def test_bad_session_does_not_prevent_other_sessions_restoring(self):
        bad = Mock()
        type(bad).InstanceIdentifier = property(lambda self: (_ for _ in ()).throw(OSError('gone')))
        music = session('music', 20, .5)
        backend = Mock()
        backend.sessions.return_value = [bad, music]
        levels = SessionLevels(backend, owner_pid=10)
        levels.apply(True, True)
        self.assertAlmostEqual(music.SimpleAudioVolume.value, .1)
        levels.restore()
        self.assertEqual(music.SimpleAudioVolume.value, .5)

    def test_settings_reject_invalid_levels(self):
        for invalid in [{'enabled': 'yes'}, {'background_ratio': -1}, {'voice_volume': 2},
                        {'release_seconds': float('nan')}, {'background_ratio': True}]:
            with self.assertRaises(ValueError):
                settings(invalid)


class DetectionTests(unittest.TestCase):
    def test_silence_and_low_stationary_noise_do_not_trigger(self):
        detector = SpeechDetector()
        noise = np.random.default_rng(7).normal(0, 30, 32000).astype('<i2')
        self.assertFalse(detector.feed(bytes(32000)))
        self.assertFalse(detector.feed(noise.tobytes()))

    def test_real_voice_detected_in_microphone_sized_chunks(self):
        with wave.open(str(Path('assets/poke/ouch.wav')), 'rb') as audio:
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertEqual(audio.getnchannels(), 1)
            source_rate = audio.getframerate()
            pcm = np.frombuffer(audio.readframes(audio.getnframes()), dtype='<i2')
        samples = np.interp(np.arange(0, len(pcm), source_rate / 16000), np.arange(len(pcm)), pcm).astype('<i2').tobytes()
        detector = SpeechDetector()
        self.assertTrue(any(detector.feed(samples[i:i + 2048]) for i in range(0, len(samples), 2048)))

    def test_short_click_does_not_trigger_and_split_frames_are_buffered(self):
        vad = Mock()
        vad.is_speech.return_value = True
        detector = SpeechDetector(vad)
        loud = np.full(320, 1000, dtype='<i2').tobytes()
        self.assertFalse(detector.feed(loud[:100]))
        self.assertFalse(detector.feed(loud[100:]))
        self.assertFalse(detector.feed(bytes(640 * 5)))
        detector.reset()
        self.assertTrue(detector.feed(loud * 3))


def wait_for(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.01)
    raise AssertionError('Timed out waiting for audio sidechain')


class WorkerTests(unittest.TestCase):
    def test_owner_voice_overlap_poke_release_and_shutdown(self):
        music = session('music', 20, .7)
        backend = Mock()
        backend.sessions.return_value = [music]
        detector = Mock()
        detector.feed.return_value = True
        events = []
        unsubscribe = bus.subscribe('audio.duck.changed', events.append)
        ducker = AudioDucker({'release_seconds': .2}, backend_factory=lambda: backend, detector_factory=lambda: detector).start()
        try:
            ducker.microphone(bytes(2048))
            wait_for(lambda: events and events[-1]['active'])
            wait_for(lambda: abs(music.SimpleAudioVolume.value - .14) < .001)
            ducker.voice('speech', True)
            ducker.voice('poke', True)
            ducker.voice('speech', False, tail=0)
            time.sleep(.25)
            self.assertTrue(events[-1]['active'])  # poke still active
            ducker.voice('poke', False, tail=.1)
            wait_for(lambda: not events[-1]['active'])
            wait_for(lambda: music.SimpleAudioVolume.value == .7)
            ducker.voice('speech', True)
            wait_for(lambda: music.SimpleAudioVolume.value < .7)
        finally:
            ducker.close()
            unsubscribe()
        self.assertEqual(music.SimpleAudioVolume.value, .7)
        self.assertFalse(ducker._thread.is_alive())
        backend.close.assert_called_once()

    def test_worker_failure_restores_and_releases_local_media(self):
        music = session('music', 20, .5)
        backend = Mock()
        backend.sessions.side_effect = [[music], RuntimeError('audio service stopped')]
        events = []
        unsubscribe = bus.subscribe('audio.duck.changed', events.append)
        ducker = AudioDucker(backend_factory=lambda: backend, detector_factory=Mock).start()
        try:
            with self.assertLogs('core.audio_ducking', level='ERROR'):
                ducker.voice('speech', True)
                wait_for(lambda: not ducker._thread.is_alive())
            self.assertEqual(music.SimpleAudioVolume.value, .5)
            self.assertFalse(events[-1]['active'])
        finally:
            ducker.close()
            unsubscribe()

    def test_disabled_has_no_worker_and_does_not_change_volume(self):
        backend = Mock()
        ducker = AudioDucker({'enabled': False}, backend_factory=backend).start()
        ducker.microphone(bytes(2048))
        ducker.voice('speech', True)
        ducker.close()
        self.assertIsNone(ducker._thread)
        backend.assert_not_called()


class IntegrationTests(unittest.TestCase):
    def test_media_window_ducks_on_gui_thread_without_muting_mic_or_poke(self):
        script = '''
import threading
from PyQt6.QtWidgets import QApplication
from core.event_bus import bus
from ui import JarvisUI
app=QApplication([]);ui=JarvisUI('face.png');w=ui._win
w._video_audio.setVolume(.7);w._video_sound_out.setVolume(.45)
def publish(active):
    bus.publish('audio.duck.changed',active=active,voice=True,ratio=.2)
t=threading.Thread(target=publish,args=(True,));t.start();t.join();app.processEvents()
assert abs(w._video_audio.volume()-.14)<.001
assert abs(w._video_sound_out.volume()-.09)<.001
assert not w._muted and not w._video_audio.isMuted()
publish(True);app.processEvents()
assert abs(w._video_audio.volume()-.14)<.001
bus.publish('audio.duck.changed',active=True,voice=True,ratio=.1);app.processEvents()
assert abs(w._video_audio.volume()-.07)<.001
publish(False);app.processEvents()
assert abs(w._video_audio.volume()-.7)<.001
assert abs(w._video_sound_out.volume()-.45)<.001
assert not w._muted and not w._video_sound_out.isMuted()
publish(True);app.processEvents();ui._shutdown_audio()
assert abs(w._video_audio.volume()-.7)<.001
ui._bar.shutdown();w._unsubscribe_runtime();w.close()
print('Audio sidechain GUI integration OK')
'''
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True,
                                encoding='utf-8', timeout=30, env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Audio sidechain GUI integration OK', result.stdout)


class MicrophoneIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_main_uses_speech_signals_and_preserves_microphone_gates(self):
        from main import JarvisLive, _TAIL_MARGIN
        from core.echo import EchoGuard
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
        live._echo = EchoGuard()
        live.out_queue = asyncio.Queue()
        pcm = np.ones((1024, 1), dtype=np.int16)
        with patch('main.sd.InputStream', return_value=MagicMock()) as stream, \
                patch('main.audio_devices.resolve', return_value=None), patch('builtins.print'):
            task = asyncio.create_task(live._listen_audio())
            try:
                await asyncio.sleep(0)
                callback = stream.call_args.kwargs['callback']
                callback(pcm, 1024, None, None)
                live._audio_ducker.microphone.assert_called_once_with(pcm.tobytes())
                live._audio_ducker.reset_mock()
                for key in ['_is_speaking', '_companion_audio_active', '_phone_active', '_ptt_enabled']:
                    setattr(live, key, True)
                    callback(pcm, 1024, None, None)
                    setattr(live, key, False)
                live.ui.muted = True
                callback(pcm, 1024, None, None)
                live.ui.muted = False
                live._wake_enabled, live._awake = True, False
                callback(pcm, 1024, None, None)
                live._audio_ducker.microphone.assert_not_called()
                live.set_speaking(True)
                live._audio_ducker.voice.assert_called_with('speech', True, tail=live._out_latency + _TAIL_MARGIN)
                live.companion_audio_activity(True)
                live._audio_ducker.voice.assert_called_with('poke', True, tail=.5)
            finally:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
