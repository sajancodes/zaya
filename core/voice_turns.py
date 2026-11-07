"""Bound spoken input while keeping capture open and retaining first syllables with adaptive silence detection."""
from collections import deque
from core.audio_ducking import SpeechDetector


class VoiceTurns:
    def __init__(
        self,
        detector=None,
        silence_seconds=None,
        prefix_blocks=6,
        min_silence_seconds=0.42,
        max_silence_seconds=0.85,
        armed_silence_seconds=0.30,
    ):
        self.detector = detector or SpeechDetector()
        self.prefix = deque(maxlen=prefix_blocks)
        self.active = False
        self.last_speech = 0.0
        self.speech_start_time = 0.0
        self.cue_armed = False

        self._static_silence = silence_seconds
        self.min_silence_seconds = min_silence_seconds
        self.max_silence_seconds = max_silence_seconds
        self.armed_silence_seconds = armed_silence_seconds

    @property
    def silence_seconds(self) -> float:
        """Backward-compatible property exposing current silence threshold."""
        return self.current_silence_threshold()

    def set_cue_armed(self, armed: bool):
        """Tighten silence boundary for ultra-fast response when a cue or trigger is armed."""
        self.cue_armed = armed

    def current_silence_threshold(self) -> float:
        """Dynamically compute the required silence duration based on speech length and armed state."""
        if self._static_silence is not None:
            return self._static_silence
        if self.cue_armed:
            return self.armed_silence_seconds
        duration = max(0.0, self.last_speech - self.speech_start_time)
        if duration < 1.5:
            return self.min_silence_seconds
        if duration >= 4.0:
            return self.max_silence_seconds
        alpha = (duration - 1.5) / 2.5
        return self.min_silence_seconds + alpha * (self.max_silence_seconds - self.min_silence_seconds)

    def feed(self, pcm, now):
        speech = self.detector.feed(pcm)
        if not self.active:
            self.prefix.append(pcm)
            if not speech:
                return [], False
            self.active = True
            self.speech_start_time = now
            self.last_speech = now
            chunks = list(self.prefix)
            self.prefix.clear()
            return chunks, False
        if speech:
            self.last_speech = now
        threshold = self.current_silence_threshold()
        ended = (now - self.last_speech) >= threshold
        if ended:
            self.active = False
            self.speech_start_time = 0.0
            self.prefix.clear()
        return [pcm], ended

    def reset(self):
        self.active = False
        self.speech_start_time = 0.0
        self.prefix.clear()
        self.detector.reset()
