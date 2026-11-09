"""Multi-Modal Audio/Visual Fusion Attention Gate (Cycle 80).
Created and developed by Sajan Rai for Zaya.

Fuses visual gaze/face tracking, acoustic voice activity, and desktop interaction kinematics
into a unified engagement and attention state. Gates proactive speech, conversational cues,
and notification delivery channels according to the owner's actual cognitive availability.
"""
from __future__ import annotations

import collections
import enum
import logging
import math
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EngagementLevel(str, enum.Enum):
    FOCUSED_DIRECT = "focused_direct"          # Directly looking at screen, talking or interacting
    COGNITIVE_ENGAGED = "cognitive_engaged"    # Actively working/typing, screen focus
    PERIPHERAL_AWARE = "peripheral_aware"      # Present in room, ambient listening
    DISTRACTED_OR_AWAY = "distracted_or_away"  # Turned away, on phone, or away from desk


@dataclass
class VisualAttentionCue:
    face_detected: bool = False
    gaze_at_screen: bool = False
    head_yaw_deg: float = 0.0      # -90 to +90
    head_pitch_deg: float = 0.0    # -90 to +90
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AcousticAttentionCue:
    voice_detected: bool = False
    is_speech_directed: bool = False
    rms_energy: float = 0.0
    confidence: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class AttentionState:
    level: EngagementLevel
    attention_score: float         # 0.0 to 1.0
    visual_score: float           # 0.0 to 1.0
    acoustic_score: float         # 0.0 to 1.0
    interaction_score: float      # 0.0 to 1.0
    recommended_channel: str      # "voice", "visual_card", "silent_notification", "mobile_remote"
    allow_proactive_speech: bool
    summary: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "attention_score": round(self.attention_score, 3),
            "visual_score": round(self.visual_score, 3),
            "acoustic_score": round(self.acoustic_score, 3),
            "interaction_score": round(self.interaction_score, 3),
            "recommended_channel": self.recommended_channel,
            "allow_proactive_speech": self.allow_proactive_speech,
            "summary": self.summary,
            "timestamp": self.timestamp,
        }


class AVAttentionFusionEngine:
    """Real-time multi-modal attention fusion gate."""

    def __init__(self, ema_alpha: float = 0.35) -> None:
        self.ema_alpha = ema_alpha
        self._lock = threading.RLock()
        self._latest_visual: Optional[VisualAttentionCue] = None
        self._latest_acoustic: Optional[AcousticAttentionCue] = None
        self._last_interaction_time: float = time.time()
        self._current_attention_score: float = 0.50
        self._history: collections.deque[AttentionState] = collections.deque(maxlen=100)

    def record_interaction(self, event_time: Optional[float] = None) -> None:
        """Record local user interaction (keystroke, mouse movement, or command)."""
        with self._lock:
            self._last_interaction_time = event_time or time.time()

    def update_visual(
        self,
        face_detected: bool,
        gaze_at_screen: bool,
        head_yaw_deg: float = 0.0,
        head_pitch_deg: float = 0.0,
        confidence: float = 0.85,
    ) -> VisualAttentionCue:
        """Ingest computer vision head-pose and gaze attention cue."""
        cue = VisualAttentionCue(
            face_detected=face_detected,
            gaze_at_screen=gaze_at_screen,
            head_yaw_deg=head_yaw_deg,
            head_pitch_deg=head_pitch_deg,
            confidence=max(0.0, min(1.0, confidence)),
            timestamp=time.time(),
        )
        with self._lock:
            self._latest_visual = cue
        return cue

    def update_acoustic(
        self,
        voice_detected: bool,
        is_speech_directed: bool = True,
        rms_energy: float = 1000.0,
        confidence: float = 0.85,
    ) -> AcousticAttentionCue:
        """Ingest acoustic speech activity and orientation cue."""
        cue = AcousticAttentionCue(
            voice_detected=voice_detected,
            is_speech_directed=is_speech_directed,
            rms_energy=rms_energy,
            confidence=max(0.0, min(1.0, confidence)),
            timestamp=time.time(),
        )
        with self._lock:
            self._latest_acoustic = cue
        return cue

    def evaluate_attention(
        self,
        current_time: Optional[float] = None,
        use_hardware_idle: bool = True,
    ) -> AttentionState:
        """Compute the instantaneous multi-modal fused attention and engagement state."""
        now = current_time or time.time()

        with self._lock:
            # 1. Interaction Score (Recency decay)
            idle_sec = max(0.0, now - self._last_interaction_time)
            # Query OS desktop idle seconds if on Windows and not in deterministic replay/test mode
            if use_hardware_idle and current_time is None:
                try:
                    from core.presence import desktop_idle_seconds
                    sys_idle = desktop_idle_seconds()
                    if sys_idle is not None:
                        idle_sec = min(idle_sec, sys_idle)
                except Exception:
                    pass

            if idle_sec < 10.0:
                interaction_score = 1.0
            elif idle_sec < 60.0:
                interaction_score = 1.0 - ((idle_sec - 10.0) / 50.0) * 0.50  # 1.0 -> 0.50
            elif idle_sec < 300.0:
                interaction_score = 0.50 - ((idle_sec - 60.0) / 240.0) * 0.35  # 0.50 -> 0.15
            else:
                interaction_score = 0.0

            # 2. Visual Score
            visual_score = 0.0
            if self._latest_visual and (now - self._latest_visual.timestamp) < 5.0:
                v = self._latest_visual
                if v.face_detected:
                    base = 0.40 * v.confidence
                    if v.gaze_at_screen or (abs(v.head_yaw_deg) <= 22.0 and abs(v.head_pitch_deg) <= 20.0):
                        base += 0.60 * v.confidence
                    visual_score = min(1.0, base)
            else:
                # If no camera stream is active, rely on interaction as proxy for visual
                visual_score = interaction_score * 0.70

            # 3. Acoustic Score
            acoustic_score = 0.0
            if self._latest_acoustic and (now - self._latest_acoustic.timestamp) < 4.0:
                a = self._latest_acoustic
                if a.voice_detected:
                    multiplier = 1.0 if a.is_speech_directed else 0.50
                    acoustic_score = min(1.0, 0.85 * a.confidence * multiplier)
            else:
                acoustic_score = 0.10

            # 4. Multi-Modal Fusion (Weighted combination)
            # Visual has highest weight when camera is present; interaction is primary fallback;
            # acoustic acts as immediate attention trigger.
            raw_fused = (
                (visual_score * 0.45)
                + (interaction_score * 0.35)
                + (acoustic_score * 0.20)
            )

            # Apply Exponential Moving Average (EMA) to prevent flickering states
            self._current_attention_score = (
                (self.ema_alpha * raw_fused) + ((1.0 - self.ema_alpha) * self._current_attention_score)
            )
            score = self._current_attention_score

            # 5. Classify Engagement Level & Delivery Policies
            if score >= 0.72 or (visual_score >= 0.80 and interaction_score >= 0.60):
                level = EngagementLevel.FOCUSED_DIRECT
                channel = "voice"
                allow_speech = True
                summary = "Owner is directly focused on screen/Zaya. Full voice and conversational fluency active."
            elif score >= 0.45:
                level = EngagementLevel.COGNITIVE_ENGAGED
                channel = "voice" if acoustic_score > 0.4 else "visual_card"
                allow_speech = True
                summary = "Owner is actively working. Brief voice responses or display cards preferred."
            elif score >= 0.20 or interaction_score > 0.15:
                level = EngagementLevel.PERIPHERAL_AWARE
                channel = "visual_card"
                allow_speech = False
                summary = "Owner is nearby or ambient. Subtle on-screen cards; avoid unsolicited vocal interruptions."
            else:
                level = EngagementLevel.DISTRACTED_OR_AWAY
                channel = "silent_notification" if idle_sec < 600 else "mobile_remote"
                allow_speech = False
                summary = "Owner is away or deeply disengaged. Route to silent dashboard or mobile remote."

            state = AttentionState(
                level=level,
                attention_score=score,
                visual_score=visual_score,
                acoustic_score=acoustic_score,
                interaction_score=interaction_score,
                recommended_channel=channel,
                allow_proactive_speech=allow_speech,
                summary=summary,
                timestamp=now,
            )

            self._history.append(state)
            return state

    def should_speak(self, urgency: str = "normal", current_time: Optional[float] = None) -> bool:
        """Fast gate for voice synthesizer — returns whether audio output should be vocalized."""
        if urgency in ("urgent", "alarm", "call"):
            return True
        state = self.evaluate_attention(current_time=current_time)
        return state.allow_proactive_speech

    def get_recent_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return [s.to_dict() for s in list(self._history)[-limit:]]


# ── Global Singleton ─────────────────────────────────────────────────────────

_av_gate: Optional[AVAttentionFusionEngine] = None


def get_av_attention_gate() -> AVAttentionFusionEngine:
    global _av_gate
    if _av_gate is None:
        _av_gate = AVAttentionFusionEngine()
    return _av_gate
