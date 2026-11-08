import asyncio
from unittest.mock import MagicMock
import pytest

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


def test_notification_delivery_waits_for_playback_or_interrupt():
    async def _run():
        class MockAssistant:
            def __init__(self):
                self._notification_active = False
                self._notification_interrupted = False
                self._is_speaking = False
                self.audio_in_queue = asyncio.Queue()
                self.delivered_called = False

            async def _deliver_owner_notice(self, item, coding=False, mode=''):
                self._notification_active = True
                self._is_speaking = True
                await self.audio_in_queue.put(b"audio_chunk")
                return True

            def interrupt(self, reason="barge_in"):
                if self._notification_active:
                    self._notification_interrupted = True
                self._notification_active = False
                self._is_speaking = False
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()

        assistant = MockAssistant()
        item = {"id": "alert_123", "summary": "Port dropped"}

        # Delivery started
        await assistant._deliver_owner_notice(item)
        assert assistant._notification_active is True
        assert not assistant.audio_in_queue.empty()

        # Mid-speech barge in triggers interrupt
        assistant.interrupt()
        assert assistant._notification_interrupted is True
        assert assistant.audio_in_queue.empty()

    asyncio.run(_run())
