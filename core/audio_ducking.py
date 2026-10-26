"""Local speech sidechain and reversible Windows per-session audio levels.

The microphone callback only enqueues PCM. COM and VAD run on one worker;
microphone mute, session mute and the system master volume are never changed.
"""
from collections import deque
import atexit
import logging
import math
import os
import queue
import sys
import threading
import time

from core.event_bus import bus

log = logging.getLogger(__name__)
DEFAULTS = {'enabled': True, 'background_ratio': .2, 'voice_volume': 1.0,
            'release_seconds': .8}


def settings(value=None):
    value = {} if value is None else value
    if not isinstance(value, dict):
        raise ValueError('audio_ducking must be a JSON object.')
    result = {**DEFAULTS, **value}
    if not isinstance(result['enabled'], bool):
        raise ValueError('audio_ducking.enabled must be true or false.')
    for name, low, high in [('background_ratio', .05, 1), ('voice_volume', 0, 1),
                            ('release_seconds', .2, 3)]:
        number = result[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or not low <= number <= high:
            raise ValueError(f'audio_ducking.{name} must be between {low} and {high}.')
    return result


class SpeechDetector:
    """20 ms WebRTC frames, requiring sustained speech instead of peak volume."""
    def __init__(self, vad=None, aggressiveness=3):
        self._fallback_bands = None
        if vad is None:
            try:
                import webrtcvad
            except ImportError:
                log.warning(
                    'WebRTC VAD unavailable; using conservative spectral speech detection'
                )
            else:
                vad = webrtcvad.Vad(aggressiveness)
        self.vad = vad
        self.buffer = bytearray()
        self.recent = deque(maxlen=5)

    def feed(self, pcm):
        import numpy as np
        if len(pcm) % 2:
            raise ValueError('SpeechDetector requires signed 16-bit PCM.')
        self.buffer.extend(pcm)
        speech = False
        while len(self.buffer) >= 640:  # mono PCM16, 16 kHz, 20 ms
            frame = bytes(self.buffer[:640])
            del self.buffer[:640]
            samples = np.frombuffer(frame, dtype='<i2').astype(np.float32)
            audible = float(np.sqrt(np.mean(samples * samples))) >= 260
            spectrum_changed = self._speech_spectrum_changed(samples)
            detected = (
                self.vad.is_speech(frame, 16000)
                if self.vad is not None else spectrum_changed
            )
            self.recent.append(audible and detected and spectrum_changed)
            speech |= sum(self.recent) >= 3 and self.recent[-1]
        return speech

    def _speech_spectrum_changed(self, samples):
        """Require changing speech-band shape to reject stationary room noise."""
        import numpy as np

        windowed = samples * np.hanning(samples.size)
        power = np.abs(np.fft.rfft(windowed)) ** 2
        frequencies = np.fft.rfftfreq(samples.size, 1 / 16000)
        edges = (200, 500, 900, 1500, 2500, 3800)
        bands = np.array([
            power[(frequencies >= low) & (frequencies < high)].sum()
            for low, high in zip(edges, edges[1:])
        ], dtype=np.float64)
        total = float(power.sum())
        speech_band = float(bands.sum())
        if total <= 0 or speech_band / total < 0.55:
            self._fallback_bands = bands
            return False

        current = bands / max(speech_band, 1e-12)
        previous = self._fallback_bands
        self._fallback_bands = bands
        if previous is None:
            return False
        previous = previous / max(float(previous.sum()), 1e-12)
        spectral_change = float(np.abs(current - previous).sum()) / 2
        return spectral_change >= 0.08

    def reset(self):
        self.buffer.clear()
        self.recent.clear()
        self._fallback_bands = None


class WindowsSessions:
    """Enumerate render sessions on every connected output, on the COM thread."""
    def __init__(self):
        import comtypes
        comtypes.CoInitialize()
        self.comtypes = comtypes

    def sessions(self):
        from pycaw.pycaw import AudioUtilities, AudioSession, IAudioSessionControl2
        # Use raw endpoints to avoid reading unrelated device property stores.
        collection = AudioUtilities.GetDeviceEnumerator().EnumAudioEndpoints(0, 1)
        from pycaw.api.audiopolicy import IAudioSessionManager2
        for index in range(collection.GetCount()):
            try:
                endpoint = collection.Item(index)
                manager = endpoint.Activate(IAudioSessionManager2._iid_, self.comtypes.CLSCTX_ALL, None).QueryInterface(IAudioSessionManager2)
                enumerator = manager.GetSessionEnumerator()
                for number in range(enumerator.GetCount()):
                    control = enumerator.GetSession(number).QueryInterface(IAudioSessionControl2)
                    yield AudioSession(control)
            except Exception:
                log.debug('Audio endpoint unavailable', exc_info=True)

    def close(self):
        self.comtypes.CoUninitialize()


class SessionLevels:
    """Keep each session's original level; respect manual adjustments and mute."""
    def __init__(self, backend, owner_pid=None, background_ratio=.2, voice_volume=1):
        self.backend = backend
        self.owner_pid = os.getpid() if owner_pid is None else owner_pid
        self.ratio = background_ratio
        self.voice_volume = voice_volume
        self.saved = {}
        self.media_ratio = background_ratio

    def apply(self, active, voice):
        self.media_ratio = self.ratio
        if not active:
            self.restore()
            return
        for session in self.backend.sessions():
            try:
                key = session.InstanceIdentifier
                own = session.ProcessId == self.owner_pid
                volume = session.SimpleAudioVolume
                if own and not voice:
                    self._restore_one(key)
                    continue
                original, last = self.saved.get(key, (None, None, None))[1:]
                current = volume.GetMasterVolume()
                if original is None:
                    original = current
                elif abs(current - last) > .005:
                    # A user moved this session's slider while ducked. Their new
                    # value becomes the baseline, so restore won't undo it.
                    original = current
                target = max(original, self.voice_volume) if own else original * self.ratio
                self.saved[key] = (volume, original, target)
                if abs(current - target) > .001:
                    volume.SetMasterVolume(target, None)
                if own and target > 0:
                    # Qt media shares the process with voice. Compensate its
                    # local output level for any increase in the session mixer,
                    # so a quiet original session cannot make music louder.
                    self.media_ratio = min(self.media_ratio, self.ratio * original / target)
            except Exception:
                log.debug('Audio session disappeared', exc_info=True)

    def _restore_one(self, key):
        item = self.saved.get(key)
        if item is None:
            return
        volume, original, last = item
        try:
            if abs(volume.GetMasterVolume() - last) <= .005:
                volume.SetMasterVolume(original, None)
            self.saved.pop(key, None)
        except Exception:
            log.debug('Audio session restore unavailable', exc_info=True)

    def restore(self):
        for key in list(self.saved):
            self._restore_one(key)


class AudioDucker:
    def __init__(self, config=None, backend_factory=None, detector_factory=SpeechDetector):
        self.config = settings(config)
        self.backend_factory = backend_factory or (WindowsSessions if sys.platform == 'win32' else None)
        self.detector_factory = detector_factory
        self._pcm = queue.Queue(maxsize=6)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._voices = set()
        self._voice_until = self._owner_until = 0.0
        self._thread = None

    def start(self):
        if self.config['enabled'] and self._thread is None and not self._stop.is_set():
            self._thread = threading.Thread(target=self._run, name='zaya-audio-duck', daemon=True)
            self._thread.start()
            atexit.register(self.close)
        return self

    def voice(self, source, active, tail=.3):
        with self._lock:
            if active:
                self._voices.add(source)
            elif source in self._voices:
                self._voices.discard(source)
                self._voice_until = time.monotonic() + tail
        self._wake.set()

    def microphone(self, pcm):
        if self.config['enabled'] and not self._stop.is_set():
            try:
                self._pcm.put_nowait(pcm)
                self._wake.set()
            except queue.Full:
                pass

    def _run(self):
        backend = levels = detector = None
        previous = (False, False, 1.0)
        last_apply = 0.0
        try:
            if self.backend_factory:
                try:
                    backend = self.backend_factory()
                    levels = SessionLevels(backend, background_ratio=self.config['background_ratio'], voice_volume=self.config['voice_volume'])
                except Exception:
                    log.exception('Windows audio ducking unavailable; local media still supported')
            try:
                detector = self.detector_factory()
            except Exception:
                log.exception('Local speech detection unavailable')
            while not self._stop.is_set():
                self._wake.wait(.1)
                self._wake.clear()
                while not self._pcm.empty():
                    pcm = self._pcm.get_nowait()
                    if detector and detector.feed(pcm):
                        self._owner_until = time.monotonic() + self.config['release_seconds']
                now = time.monotonic()
                with self._lock:
                    voice = bool(self._voices) or now < self._voice_until
                active = voice or now < self._owner_until
                changed = (active, voice) != previous[:2]
                if levels and (changed or now - last_apply >= .25):
                    levels.apply(active, voice)
                    last_apply = now
                ratio = (levels.media_ratio if levels else self.config['background_ratio']) if active else 1.0
                state = (active, voice, ratio)
                if state != previous:
                    bus.publish('audio.duck.changed', active=active, voice=voice, ratio=ratio)
                    previous = state
        except Exception:
            log.exception('Audio ducking stopped; restoring session levels')
        finally:
            try:
                if levels:
                    levels.restore()
            finally:
                try:
                    if backend:
                        backend.close()
                finally:
                    bus.publish('audio.duck.changed', active=False, voice=False, ratio=1.0)

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
