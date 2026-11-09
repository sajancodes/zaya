"""Tests for Acoustic Scene & Sound Event Classifier (Cycle 75).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import math
import struct
import pytest

from core.acoustic_scene import AcousticSceneClassifier, SoundEvent
from actions.acoustic_scene_action import handle_acoustic_scene


def _generate_sine_pcm(freq_hz: float, duration_sec: float = 0.1, sample_rate: int = 16000, amplitude: float = 6000.0) -> bytes:
    """Generate 16-bit mono PCM bytes for a sine wave."""
    samples = []
    num_samples = int(duration_sec * sample_rate)
    for i in range(num_samples):
        val = int(amplitude * math.sin(2.0 * math.pi * freq_hz * (i / sample_rate)))
        samples.append(max(-32768, min(32767, val)))
    return struct.pack(f"<{len(samples)}h", *samples)


def _generate_knock_pcm(sample_rate: int = 16000) -> bytes:
    """Generate a low frequency impulsive burst resembling a knock."""
    samples = []
    # 50ms of sharp 150Hz thump with rapid decay
    num_samples = int(0.05 * sample_rate)
    for i in range(num_samples):
        decay = math.exp(-i / (0.01 * sample_rate))
        val = int(8000.0 * decay * math.sin(2.0 * math.pi * 180.0 * (i / sample_rate)))
        samples.append(max(-32768, min(32767, val)))
    return struct.pack(f"<{len(samples)}h", *samples)


class TestAcousticScene:
    def test_alarm_chirp_detection(self):
        classifier = AcousticSceneClassifier(cooldown_sec=0.1)
        pcm = _generate_sine_pcm(freq_hz=3000.0, duration_sec=0.1, amplitude=5000.0)

        event = classifier.analyze_frame(pcm)
        assert event is not None
        assert event.category == "alarm_chirp"
        assert event.frequency_hz is not None
        assert 2500 <= event.frequency_hz <= 3500
        assert event.confidence >= 0.70

    def test_door_knock_detection(self):
        classifier = AcousticSceneClassifier(cooldown_sec=0.1)
        pcm = _generate_knock_pcm()

        event = classifier.analyze_frame(pcm)
        assert event is not None
        assert event.category == "door_knock"
        assert "door knock" in event.description.lower()

    def test_silence_returns_none(self):
        classifier = AcousticSceneClassifier()
        # Flat zeros
        pcm = struct.pack("<1000h", *([0] * 1000))
        assert classifier.analyze_frame(pcm) is None

    def test_cooldown_suppression(self):
        classifier = AcousticSceneClassifier(cooldown_sec=5.0)
        pcm = _generate_sine_pcm(freq_hz=3000.0, duration_sec=0.1, amplitude=5000.0)

        ev1 = classifier.analyze_frame(pcm)
        assert ev1 is not None

        # Immediate next frame should be suppressed by cooldown
        ev2 = classifier.analyze_frame(pcm)
        assert ev2 is None

    def test_toggle_category(self):
        classifier = AcousticSceneClassifier(cooldown_sec=0.0)
        classifier.set_category_enabled("alarm_chirp", False)

        pcm = _generate_sine_pcm(freq_hz=3000.0, duration_sec=0.1, amplitude=5000.0)
        assert classifier.analyze_frame(pcm) is None

        classifier.set_category_enabled("alarm_chirp", True)
        assert classifier.analyze_frame(pcm) is not None


class TestAcousticSceneAction:
    def test_action_status_and_toggle(self):
        res = handle_acoustic_scene(action="status")
        data = json.loads(res)
        assert data["status"] == "success"
        assert "door_knock" in data["enabled_categories"]

        toggle_res = handle_acoustic_scene(action="toggle", category="glass_break", enabled=False)
        toggle_data = json.loads(toggle_res)
        assert toggle_data["status"] == "success"
        assert toggle_data["enabled"] is False
