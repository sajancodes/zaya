"""Tests for Voiceprint Biometrics and Speaker Verification Guard.
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import base64
import math
import struct
import tempfile
from pathlib import Path
import pytest

from core.execution_policy import TRUST_EXTERNAL_MESSAGE, with_trust
from core.voice_biometrics import (
    VoiceprintManager,
    extract_features,
)
from actions.voiceprint_guard import voiceprint_guard


def generate_pcm_sine(freq_hz: float, duration_sec: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate 16-bit mono PCM sine wave audio bytes."""
    num_samples = int(duration_sec * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / float(sample_rate)
        val = int(16000 * math.sin(2 * math.pi * freq_hz * t))
        samples.append(val)
    return struct.pack(f"<{num_samples}h", *samples)


@pytest.fixture
def temp_voiceprint_mgr():
    with tempfile.TemporaryDirectory() as td:
        profile_path = Path(td) / "voiceprint_profile.json"
        mgr = VoiceprintManager(profile_path=profile_path)
        yield mgr


def test_acoustic_feature_extraction():
    pcm = generate_pcm_sine(freq_hz=200.0, duration_sec=0.4, sample_rate=16000)
    feat = extract_features(pcm, sample_rate=16000)
    assert feat is not None
    assert feat.energy_rms > 0.05
    # Pitch should detect around 200 Hz
    assert 180 <= feat.pitch_hz <= 220
    assert feat.spectral_centroid_hz > 100.0


def test_voiceprint_enrollment_and_verification(temp_voiceprint_mgr):
    mgr = temp_voiceprint_mgr
    # Before enrollment, status is not enrolled and verify is permissive
    pcm_tone = generate_pcm_sine(freq_hz=160.0, duration_sec=0.5)
    un_res = mgr.verify(pcm_tone)
    assert un_res.enrolled is False
    assert un_res.match is True

    # Enroll sample
    ok, msg = mgr.enroll(pcm_tone)
    assert ok is True
    assert mgr.status()["enrolled"] is True

    # Verify matching audio (same pitch)
    pcm_match = generate_pcm_sine(freq_hz=162.0, duration_sec=0.5)
    res_match = mgr.verify(pcm_match, threshold=0.55)
    assert res_match.match is True
    assert res_match.confidence > 0.70

    # Verify mismatching audio (very different pitch e.g. 350 Hz)
    pcm_mismatch = generate_pcm_sine(freq_hz=350.0, duration_sec=0.5)
    res_mismatch = mgr.verify(pcm_mismatch, threshold=0.55)
    assert res_mismatch.match is False
    assert res_mismatch.distance > 0.55


def test_voiceprint_reset(temp_voiceprint_mgr):
    mgr = temp_voiceprint_mgr
    pcm = generate_pcm_sine(freq_hz=150.0, duration_sec=0.5)
    mgr.enroll(pcm)
    assert mgr.status()["enrolled"] is True

    mgr.reset()
    assert mgr.status()["enrolled"] is False
    assert mgr.status()["samples_count"] == 0


def test_voiceprint_guard_action(temp_voiceprint_mgr, monkeypatch):
    monkeypatch.setattr("actions.voiceprint_guard.get_voiceprint_manager", lambda: temp_voiceprint_mgr)

    # Status
    st_res = voiceprint_guard({"action": "status"})
    assert st_res.status == "success"
    assert st_res.data["enrolled"] is False

    # Enroll
    pcm = generate_pcm_sine(freq_hz=180.0, duration_sec=0.5)
    b64_audio = base64.b64encode(pcm).decode("ascii")

    en_res = voiceprint_guard({"action": "enroll", "audio_b64": b64_audio})
    assert en_res.status == "success"
    assert en_res.data["enrolled"] is True

    # Verify
    vf_res = voiceprint_guard({"action": "verify", "audio_b64": b64_audio})
    assert vf_res.status == "success"
    assert vf_res.data["match"] is True

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            voiceprint_guard({"action": "status"})
