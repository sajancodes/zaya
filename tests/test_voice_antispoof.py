"""Tests for Voiceprint Anti-Spoofing & Replay Attack Defense (Cycle 78).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import math
import struct
import pytest

from core.voice_antispoof import VoiceAntiSpoofEngine, LivenessResult
from actions.voice_antispoof_action import handle_voice_antispoof


def _generate_natural_speech_pcm(sample_rate: int = 16000, duration_sec: float = 0.2) -> bytes:
    """Generate simulated live speech PCM with natural glottal pulses and aerodynamic asymmetry."""
    samples = []
    num_samples = int(duration_sec * sample_rate)
    f0 = 130.0  # Fundamental frequency (Hz)
    for i in range(num_samples):
        t = i / sample_rate
        # Natural syllabic rise/fall envelope
        envelope = 0.4 + 0.6 * math.sin(2.0 * math.pi * 4.0 * t)
        # Glottal pulse harmonic series
        v = (
            math.sin(2.0 * math.pi * f0 * t)
            + 0.6 * math.sin(2.0 * math.pi * 2 * f0 * t)
            + 0.3 * math.sin(2.0 * math.pi * 3 * f0 * t)
        )
        # Aerodynamic air asymmetry (plosive bias)
        v = (v * envelope) + 0.15 * math.sin(2.0 * math.pi * 35.0 * t)
        val = int(v * 4500.0)
        samples.append(max(-32768, min(32767, val)))
    return struct.pack(f"<{len(samples)}h", *samples)


def _generate_synthetic_flat_pcm(sample_rate: int = 16000, duration_sec: float = 0.2) -> bytes:
    """Generate heavily compressed, flat audio resembling a compressed speaker transducer."""
    samples = []
    num_samples = int(duration_sec * sample_rate)
    for i in range(num_samples):
        # Flat square-like wave with low dynamic range and zero low-end
        val = 1500 if (i % 20 < 10) else -1500
        samples.append(val)
    return struct.pack(f"<{len(samples)}h", *samples)


class TestVoiceAntiSpoof:
    def test_natural_speech_passes_liveness(self):
        engine = VoiceAntiSpoofEngine(liveness_threshold=0.45)
        pcm = _generate_natural_speech_pcm()

        result = engine.evaluate_pcm(pcm)
        assert result.is_live is True
        assert result.liveness_score >= 0.45
        assert "Passed physical acoustic liveness check" in result.decision_reason

    def test_synthetic_flat_audio_flagged(self):
        engine = VoiceAntiSpoofEngine(liveness_threshold=0.60)
        pcm = _generate_synthetic_flat_pcm()

        result = engine.evaluate_pcm(pcm)
        assert result.is_live is False
        assert "potential replay or synthetic" in result.decision_reason

    def test_insufficient_samples_handling(self):
        engine = VoiceAntiSpoofEngine()
        result = engine.evaluate_pcm(b"")
        assert result.is_live is False
        assert "Insufficient" in result.decision_reason

    def test_set_threshold(self):
        engine = VoiceAntiSpoofEngine()
        th = engine.set_threshold(0.75)
        assert th == 0.75
        assert engine.liveness_threshold == 0.75


class TestVoiceAntiSpoofAction:
    def test_action_status_and_set_threshold(self):
        res = handle_voice_antispoof(action="status")
        data = json.loads(res)
        assert data["status"] == "success"
        assert "threshold" in data

        res2 = handle_voice_antispoof(action="set_threshold", threshold=0.65)
        data2 = json.loads(res2)
        assert data2["status"] == "success"
        assert data2["threshold"] == 0.65
