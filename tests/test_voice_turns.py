import pytest
from core.voice_turns import VoiceTurns


class DummyDetector:
    def __init__(self, speech_sequence):
        self.seq = list(speech_sequence)
        self.idx = 0

    def feed(self, pcm):
        if self.idx < len(self.seq):
            val = self.seq[self.idx]
            self.idx += 1
            return val
        return False

    def reset(self):
        self.idx = 0


def test_voice_turns_short_command_fast_cutoff():
    # 3 speech blocks followed by silence
    det = DummyDetector([True, True, True, False, False, False, False])
    turns = VoiceTurns(detector=det, min_silence_seconds=0.40, max_silence_seconds=0.80)

    # First block: speech starts at t=1.0
    chunks, ended = turns.feed(b"block1", now=1.0)
    assert turns.active is True
    assert ended is False

    # Second block at t=1.1
    chunks, ended = turns.feed(b"block2", now=1.1)
    assert ended is False

    # Third block at t=1.2 (speech ends here, duration = 0.2s < 1.5s -> min silence 0.40s)
    chunks, ended = turns.feed(b"block3", now=1.2)
    assert ended is False

    # Fourth block (silence) at t=1.5 (elapsed = 0.3s < 0.40s)
    chunks, ended = turns.feed(b"block4", now=1.5)
    assert ended is False

    # Fifth block (silence) at t=1.65 (elapsed = 0.45s >= 0.40s -> ended!)
    chunks, ended = turns.feed(b"block5", now=1.65)
    assert ended is True
    assert turns.active is False


def test_voice_turns_armed_cue_instant_cutoff():
    det = DummyDetector([True, False, False])
    turns = VoiceTurns(detector=det, armed_silence_seconds=0.25)
    turns.set_cue_armed(True)

    # Speech at t=1.0
    turns.feed(b"cue_word", now=1.0)
    assert turns.active is True

    # Silence at t=1.2 (0.2s < 0.25s)
    _, ended = turns.feed(b"silence1", now=1.2)
    assert ended is False

    # Silence at t=1.26 (0.26s >= 0.25s -> ended!)
    _, ended = turns.feed(b"silence2", now=1.26)
    assert ended is True
    assert turns.active is False


def test_voice_turns_backward_compatibility_static_silence():
    det = DummyDetector([True, False, False])
    turns = VoiceTurns(detector=det, silence_seconds=0.90)

    turns.feed(b"speech", now=1.0)
    # At t=1.5 (0.5s elapsed), static 0.90s should NOT end
    _, ended = turns.feed(b"silence", now=1.5)
    assert ended is False
    assert turns.active is True

    # At t=1.95 (0.95s elapsed), static 0.90s should end
    _, ended = turns.feed(b"silence", now=1.95)
    assert ended is True
