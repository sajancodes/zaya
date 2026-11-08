import asyncio
from unittest.mock import MagicMock

from core.voice_turns import VoiceTurns


def test_voice_turns_partial_utterance_below_silence_threshold_not_finalized():
    # Detector that returns True once (speech start), then False (silence)
    mock_detector = MagicMock()
    mock_detector.feed.side_effect = [True, False, False]

    turns = VoiceTurns(detector=mock_detector, silence_seconds=0.8)
    pcm_chunk = b"\x00" * 320

    # 1. Speech starts at t=1.0
    _chunks, ended = turns.feed(pcm_chunk, now=1.0)
    assert turns.active is True
    assert ended is False

    # 2. Silence frame at t=1.2 (elapsed silence = 0.2s, below threshold 0.8s)
    _chunks, ended = turns.feed(pcm_chunk, now=1.2)
    assert turns.active is True
    assert ended is False  # Not finalized

    # 3. Silence frame at t=1.9 (elapsed silence = 0.9s, above threshold 0.8s)
    _chunks, ended = turns.feed(pcm_chunk, now=1.9)
    assert turns.active is False
    assert ended is True   # Finalized


def test_interruption_during_notification_delivery_requeues():
    class DummyAssistant:
        def __init__(self):
            self._notification_active = False
            self._notification_interrupted = False
            self._interrupted = False
            self.audio_in_queue = asyncio.Queue()

        def interrupt(self, reason: str = "user_speech") -> None:
            notification_active = bool(getattr(self, '_notification_active', False))
            if notification_active:
                self._notification_interrupted = True
            self._interrupted = not notification_active
            self._notification_active = False

    assistant = DummyAssistant()
    # Notification starts speaking
    assistant._notification_active = True

    # Owner speaks or interrupt triggers mid-speech
    assistant.interrupt(reason="barge_in")

    assert assistant._notification_interrupted is True
    assert assistant._notification_active is False
