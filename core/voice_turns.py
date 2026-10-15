"""Bound spoken input while keeping capture open and retaining first syllables."""
from collections import deque
from core.audio_ducking import SpeechDetector


class VoiceTurns:
    def __init__(self, detector=None, silence_seconds=.9, prefix_blocks=6):
        self.detector = detector or SpeechDetector()
        self.silence_seconds = silence_seconds
        self.prefix = deque(maxlen=prefix_blocks)
        self.active = False
        self.last_speech = 0.0

    def feed(self, pcm, now):
        speech = self.detector.feed(pcm)
        if not self.active:
            self.prefix.append(pcm)
            if not speech:
                return [], False
            self.active = True
            self.last_speech = now
            chunks = list(self.prefix)
            self.prefix.clear()
            return chunks, False
        if speech:
            self.last_speech = now
        ended = now - self.last_speech >= self.silence_seconds
        if ended:
            self.active = False
            self.prefix.clear()
        return [pcm], ended

    def reset(self):
        self.active = False
        self.prefix.clear()
        self.detector.reset()
