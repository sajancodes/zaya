"""Tests for Multi-Modal Audio/Visual Fusion Attention Gate (Cycle 80).
Created and developed by Sajan Rai for Zaya.
"""
from __future__ import annotations

import json
import time
import pytest

from core.av_attention_fusion import (
    AVAttentionFusionEngine,
    EngagementLevel,
    get_av_attention_gate,
)
from actions.av_attention_action import handle_av_attention


class TestAVAttentionFusion:
    def test_direct_focus_evaluation(self):
        engine = AVAttentionFusionEngine(ema_alpha=1.0)  # Direct instant update for deterministic test
        now = time.time()
        engine.record_interaction(event_time=now)
        engine.update_visual(face_detected=True, gaze_at_screen=True, confidence=0.95)
        engine.update_acoustic(voice_detected=True, is_speech_directed=True, confidence=0.90)

        state = engine.evaluate_attention(current_time=now)
        assert state.level == EngagementLevel.FOCUSED_DIRECT
        assert state.attention_score >= 0.70
        assert state.allow_proactive_speech is True
        assert state.recommended_channel == "voice"

    def test_distracted_away_state(self):
        engine = AVAttentionFusionEngine(ema_alpha=1.0)
        # 10 minutes ago
        now = time.time()
        engine.record_interaction(event_time=now - 700.0)
        engine.update_visual(face_detected=False, gaze_at_screen=False, confidence=0.0)
        engine._latest_visual.timestamp = now - 100.0

        state = engine.evaluate_attention(current_time=now)
        assert state.level == EngagementLevel.DISTRACTED_OR_AWAY
        assert state.attention_score < 0.25
        assert state.allow_proactive_speech is False
        assert state.recommended_channel in ("silent_notification", "mobile_remote")

    def test_peripheral_state(self):
        engine = AVAttentionFusionEngine(ema_alpha=1.0)
        now = time.time()
        # 2 minutes idle, face detected but head turned away
        engine.record_interaction(event_time=now - 120.0)
        engine.update_visual(face_detected=True, gaze_at_screen=False, head_yaw_deg=45.0, confidence=0.8)

        state = engine.evaluate_attention(current_time=now)
        assert state.level in (EngagementLevel.PERIPHERAL_AWARE, EngagementLevel.COGNITIVE_ENGAGED)
        assert state.visual_score > 0.0

    def test_should_speak_urgency_override(self):
        engine = AVAttentionFusionEngine(ema_alpha=1.0)
        now = time.time()
        engine.record_interaction(event_time=now - 1000.0)
        # Normally should_speak is False when away
        assert engine.should_speak(urgency="normal", current_time=now) is False
        # But urgent or alarm overrides gate
        assert engine.should_speak(urgency="urgent", current_time=now) is True
        assert engine.should_speak(urgency="alarm", current_time=now) is True

    def test_ema_smoothing(self):
        # With default alpha 0.35, a single instantaneous zero frame shouldn't drop score to 0
        engine = AVAttentionFusionEngine(ema_alpha=0.35)
        now = time.time()
        engine._current_attention_score = 0.80

        # Simulate one sudden idle frame
        engine._last_interaction_time = now - 500.0
        state = engine.evaluate_attention(current_time=now)
        # Should smoothly decline rather than plummeting immediately to 0
        assert state.attention_score > 0.30


class TestAVAttentionAction:
    def test_action_status_and_evaluation(self):
        res = handle_av_attention(action="status")
        data = json.loads(res)
        assert data["status"] == "success"
        assert "current_state" in data

    def test_record_cue_and_should_speak(self):
        res = handle_av_attention(
            action="record_cue",
            face_detected=True,
            gaze_at_screen=True,
            voice_detected=True,
        )
        data = json.loads(res)
        assert data["status"] == "success"
        assert "resulting_state" in data

        res2 = handle_av_attention(action="should_speak", urgency="urgent")
        data2 = json.loads(res2)
        assert data2["status"] == "success"
        assert data2["should_speak"] is True
