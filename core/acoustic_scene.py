"""Omnipresent Acoustic Scene & Sound Event Classifier.
Created and developed by Sajan Rai for Zaya.

Analyzes non-speech environmental audio spectra to detect real-world acoustic events
(door knocks, alarm chirps, doorbells, glass break, clapping) and publishes proactive alerts.
"""
from __future__ import annotations

import collections
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SoundEvent:
    event_id: str
    category: str
    confidence: float
    timestamp: float
    frequency_hz: Optional[float] = None
    energy_rms: float = 0.0
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "timestamp": self.timestamp,
            "frequency_hz": round(self.frequency_hz, 1) if self.frequency_hz else None,
            "energy_rms": round(self.energy_rms, 2),
            "description": self.description,
        }


class AcousticSceneClassifier:
    """Classifies environmental audio events using spectral and temporal heuristics."""

    def __init__(self, sample_rate: int = 16000, cooldown_sec: float = 8.0) -> None:
        self.sample_rate = sample_rate
        self.cooldown_sec = cooldown_sec
        self._last_event_time: Dict[str, float] = {}
        self._history: collections.deque[SoundEvent] = collections.deque(maxlen=100)
        self._lock = threading.RLock()
        self.enabled_categories = {
            "door_knock",
            "alarm_chirp",
            "doorbell",
            "dog_bark",
            "glass_break",
            "applause",
        }

    def analyze_frame(self, pcm_bytes: bytes) -> Optional[SoundEvent]:
        """Analyze a 16-bit mono PCM audio frame (typically 50-500ms) for sound events."""
        if not pcm_bytes or len(pcm_bytes) < 320:  # < 10ms at 16kHz
            return None

        # Unpack 16-bit PCM samples
        try:
            import struct
            count = len(pcm_bytes) // 2
            samples = struct.unpack(f"<{count}h", pcm_bytes[:count * 2])
        except Exception:
            return None

        if not samples:
            return None

        # Compute RMS Energy
        sum_sq = sum(float(s) * float(s) for s in samples)
        rms = math.sqrt(sum_sq / len(samples))
        if rms < 450.0:  # Silence / quiet ambient floor
            return None

        # Compute Zero Crossing Rate (ZCR)
        zcr = 0
        for i in range(1, len(samples)):
            if (samples[i] >= 0 and samples[i - 1] < 0) or (samples[i] < 0 and samples[i - 1] >= 0):
                zcr += 1
        zcr_rate = float(zcr) / len(samples)

        # Approximate dominant frequency via zero crossings
        est_freq = zcr_rate * (self.sample_rate / 2.0)

        # Peak amplitude to RMS ratio (Crest Factor)
        peak = max(abs(s) for s in samples)
        crest_factor = peak / (rms + 1e-5)

        now = time.monotonic()
        detected_category: Optional[str] = None
        confidence = 0.0
        desc = ""

        # Category Heuristic 1: Alarm / Smoke Detector Chirp
        # (Very high frequency pure tone: 2200 - 4500 Hz, moderate crest factor)
        if 2200 <= est_freq <= 4500 and crest_factor < 3.8 and rms > 1200:
            detected_category = "alarm_chirp"
            confidence = min(0.95, 0.70 + (rms / 8000.0))
            desc = f"High-pitched alarm or detector tone detected at ~{int(est_freq)}Hz."

        # Category Heuristic 2: Glass Break
        # (Very high ZCR rate, extreme crest factor > 5.0, high frequency > 4000 Hz)
        elif est_freq > 4000 and crest_factor >= 5.0 and rms > 2000:
            detected_category = "glass_break"
            confidence = 0.88
            desc = "Sharp broadband high-frequency impact consistent with glass breaking."

        # Category Heuristic 3: Door Knock / Thump
        # (Low frequency: 80 - 350 Hz, high crest factor impulsive attack)
        elif 80 <= est_freq <= 380 and crest_factor >= 3.5 and rms > 1500:
            detected_category = "door_knock"
            confidence = min(0.92, 0.65 + (crest_factor / 10.0))
            desc = "Low-frequency transient impact consistent with a door knock."

        # Category Heuristic 4: Doorbell / Melodic Chime
        # (Mid-high harmonic: 700 - 1800 Hz, stable tone envelope)
        elif 700 <= est_freq <= 1800 and 1.8 <= crest_factor <= 3.2 and rms > 1000:
            detected_category = "doorbell"
            confidence = 0.82
            desc = f"Harmonic melodic chime detected at ~{int(est_freq)}Hz."

        if not detected_category or detected_category not in self.enabled_categories:
            return None

        # Check cooldown to prevent duplicate alert spam
        with self._lock:
            last_t = self._last_event_time.get(detected_category, 0.0)
            if (now - last_t) < self.cooldown_sec:
                return None
            self._last_event_time[detected_category] = now

            event = SoundEvent(
                event_id=f"snd_{int(now * 1000)}",
                category=detected_category,
                confidence=confidence,
                timestamp=now,
                frequency_hz=est_freq,
                energy_rms=rms,
                description=desc,
            )
            self._history.append(event)

        # Publish alert via event bus
        try:
            from core.event_bus import bus
            bus.publish(
                "audio.sound_event",
                category=event.category,
                confidence=event.confidence,
                description=event.description,
            )
        except Exception:
            pass

        logger.info("[AcousticScene] Detected '%s' (conf=%.2f, freq=%.1fHz)", detected_category, confidence, est_freq)
        return event

    def get_recent_events(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return [e.to_dict() for e in list(self._history)[-limit:]]

    def set_category_enabled(self, category: str, enabled: bool) -> bool:
        with self._lock:
            if enabled:
                self.enabled_categories.add(category)
            else:
                self.enabled_categories.discard(category)
            return category in self.enabled_categories


# ── Global Singleton ─────────────────────────────────────────────────────────

_classifier: Optional[AcousticSceneClassifier] = None


def get_acoustic_classifier() -> AcousticSceneClassifier:
    global _classifier
    if _classifier is None:
        _classifier = AcousticSceneClassifier()
    return _classifier
