"""Tests for Voice Calibration Engine and Action.
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
from core.voice_calibration import VoiceCalibrationEngine
from actions.audio_calibration_action import voice_calibration


def make_pcm(rms_val: float, duration_sec: float = 0.2, sample_rate: int = 16000) -> bytes:
    count = int(duration_sec * sample_rate)
    amplitude = int(rms_val * 32768.0 * math.sqrt(2))
    samples = [int(amplitude * math.sin(2 * math.pi * 300 * (i / sample_rate))) for i in range(count)]
    return struct.pack(f"<{count}h", *samples)


@pytest.fixture
def temp_calib_engine():
    with tempfile.TemporaryDirectory() as td:
        storage_path = Path(td) / "test_calibration.json"
        engine = VoiceCalibrationEngine(storage_path=storage_path)
        yield engine


def test_audio_frame_energy_analysis(temp_calib_engine):
    engine = temp_calib_engine
    pcm = make_pcm(rms_val=0.10)
    rms, db = engine.analyze_audio_frame(pcm)
    assert abs(rms - 0.10) < 0.02
    # 20 * log10(0.10) = -20 dB
    assert -22.0 <= db <= -18.0


def test_ambient_noise_floor_calibration(temp_calib_engine):
    engine = temp_calib_engine
    # Feed multiple quiet samples
    for _ in range(10):
        quiet_pcm = make_pcm(rms_val=0.001)  # -60 dB
        prof = engine.feed_ambient_sample(quiet_pcm)

    assert prof.noise_floor_db <= -50.0
    assert prof.samples_calibrated == 10


def test_turn_metrics_and_cadence_adaptation(temp_calib_engine):
    engine = temp_calib_engine
    speech_pcm = make_pcm(rms_val=0.08)  # ~ -22 dB

    # Deliberate speaker (pause > 0.55s) -> silence threshold increases to 0.65s
    prof_deliberate = engine.record_turn_metrics(speech_pcm, turnaround_latency_ms=250.0, inter_phrase_pause_sec=0.60)
    assert prof_deliberate.speech_cadence == "deliberate"
    assert prof_deliberate.recommended_silence_sec == 0.65
    assert prof_deliberate.last_turnaround_ms == 250.0

    # Brisk speaker (pause < 0.28s) -> silence threshold decreases to 0.35s
    prof_brisk = engine.record_turn_metrics(speech_pcm, turnaround_latency_ms=210.0, inter_phrase_pause_sec=0.20)
    assert prof_brisk.speech_cadence == "brisk"
    assert prof_brisk.recommended_silence_sec == 0.35


def test_calibration_profile_persistence(temp_calib_engine):
    engine = temp_calib_engine
    speech_pcm = make_pcm(rms_val=0.05)
    engine.record_turn_metrics(speech_pcm, turnaround_latency_ms=195.0, inter_phrase_pause_sec=0.25)

    # Reopen
    engine2 = VoiceCalibrationEngine(storage_path=engine.storage_path)
    prof = engine2.get_profile()
    assert prof.speech_cadence == "brisk"
    assert prof.last_turnaround_ms == 195.0


def test_voice_calibration_action(temp_calib_engine, monkeypatch):
    monkeypatch.setattr("actions.audio_calibration_action.get_voice_calibration_engine", lambda: temp_calib_engine)

    # Status
    res_st = voice_calibration({"action": "status"})
    assert res_st.status == "success"
    assert "Acoustic calibration" in res_st.summary

    # Feed ambient
    sample_b64 = base64.b64encode(make_pcm(0.002)).decode("ascii")
    res_feed = voice_calibration({"action": "feed_ambient", "audio_b64": sample_b64})
    assert res_feed.status == "success"

    # Unauthorized access check
    with with_trust(TRUST_EXTERNAL_MESSAGE):
        with pytest.raises(PermissionError):
            voice_calibration({"action": "status"})
