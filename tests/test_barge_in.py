import numpy as np
import pytest

from core.audio_ducking import SpeechDetector
from core.echo import BargeInGate


class SpeechSequence:
    def __init__(self, results):
        self.results = iter(results)
        self.reset_count = 0

    def feed(self, pcm):
        return next(self.results, False)

    def reset(self):
        self.reset_count += 1


def test_speech_detector_handles_pcm_across_callback_sized_blocks():
    class AlwaysSpeech:
        def is_speech(self, frame, sample_rate):
            assert len(frame) == 640
            assert sample_rate == 16000
            return True

    detector = SpeechDetector(vad=AlwaysSpeech())
    time = np.arange(320, dtype=np.float32) / 16000
    frames = [
        (np.sin(2 * np.pi * frequency * time) * 1000).astype('<i2')
        for frequency in (300, 600, 1100, 300, 600, 1100)
    ]
    pcm = np.concatenate((*frames, np.zeros(128, dtype='<i2'))).tobytes()
    assert detector.feed(pcm[:2048]) is False
    assert detector.feed(pcm[2048:]) is True
    assert detector.buffer == bytearray(pcm[-256:])


def test_speech_detector_rejects_invalid_pcm_length():
    detector = SpeechDetector(vad=object())
    with pytest.raises(ValueError, match='signed 16-bit PCM'):
        detector.feed(b'\x00')


def test_fallback_speech_detector_rejects_a_steady_tone():
    detector = SpeechDetector()
    detector.vad = None
    time = np.arange(320, dtype=np.float32) / 16000
    tone = (np.sin(2 * np.pi * 440 * time) * 1200).astype('<i2').tobytes()
    assert all(not detector.feed(tone) for _ in range(8))


def test_web_rtc_speech_detection_does_not_accept_steady_tones():
    webrtcvad = pytest.importorskip('webrtcvad')
    time = np.arange(320, dtype=np.float32) / 16000
    for frequency in (60, 120, 440):
        detector = SpeechDetector(vad=webrtcvad.Vad(2))
        tone = (np.sin(2 * np.pi * frequency * time) * 1400).astype('<i2').tobytes()
        assert all(not detector.feed(tone) for _ in range(15))


def test_fallback_speech_detector_can_confirm_changing_voiced_audio():
    detector = SpeechDetector()
    detector.vad = None
    time = np.arange(320, dtype=np.float32) / 16000
    results = []
    for frequency in (300, 300, 600, 600, 1100, 1100, 500, 500, 1400, 1400):
        frame = (np.sin(2 * np.pi * frequency * time) * 1200).astype('<i2')
        results.append(detector.feed(frame.tobytes()))
    assert any(results)


def test_barge_in_requires_both_echo_and_speech_and_keeps_short_pause():
    speech = SpeechSequence([False, True, False, True])
    gate = BargeInGate(speech)
    assert gate.feed(b'first', True, 3, when=0.00) is None
    assert gate.feed(b'second', True, 3, when=0.06) is None
    assert gate.feed(b'pause', False, 3, when=0.12) is None
    assert gate.feed(b'third', True, 3, when=0.18) == [
        b'first', b'second', b'third'
    ]


def test_barge_in_rejects_noise_and_speech_without_echo_confirmation():
    no_speech = BargeInGate(SpeechSequence([False] * 10))
    assert all(
        no_speech.feed(b'noise', True, 2, when=index * 0.05) is None
        for index in range(6)
    )

    no_echo = BargeInGate(SpeechSequence([True] * 10))
    assert all(
        no_echo.feed(b'speech', False, 2, when=index * 0.05) is None
        for index in range(6)
    )


def test_barge_in_resets_after_a_long_rejected_gap():
    speech = SpeechSequence([False] * 10)
    gate = BargeInGate(speech)
    gate.feed(b'first', True, 3, when=0.00)
    gate.feed(b'pause', False, 3, when=0.30)
    assert speech.reset_count == 1
